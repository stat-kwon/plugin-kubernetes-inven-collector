import logging

from spaceone.inventory.libs.manager import KubernetesManager
from spaceone.inventory.connector.workload.pod import PodConnector
from spaceone.inventory.model.workload.pod.cloud_service import PodResponse, PodResource
from spaceone.inventory.model.workload.pod.cloud_service_type import CLOUD_SERVICE_TYPES
from spaceone.inventory.model.workload.pod.data import Pod

_LOGGER = logging.getLogger(__name__)


class PodManager(KubernetesManager):
    connector_name = 'PodConnector'
    cloud_service_types = CLOUD_SERVICE_TYPES

    def collect_cloud_service(self, params):
        _LOGGER.debug(f'** POD Start **')
        """
        Args:
            params:
                - options
                - schema
                - secret_data
                - filter
                - zones
        Response:
            CloudServiceResponse
        """
        collected_cloud_services = []
        error_responses = []

        secret_data = params['secret_data']
        pod_name = ''

        ##################################
        # 0. Gather All Related Resources
        # List all information through connector
        ##################################
        pod_conn: PodConnector = self.locator.get_connector(self.connector_name, **params)
        list_all_pod = pod_conn.list_pod()
        #_LOGGER.debug(f'list_all_pod => {list_all_pod}')
        """
        <class 'kubernetes.client.models.v1_pod.V1Pod'>
        'V1Pod' object is not iterable
        So object cannot convert by schematics
        """

        for pod in list_all_pod:
            try:
                #_LOGGER.debug(f'pod => {pod.to_dict()}')
                ##################################
                # 1. Set Basic Information
                ##################################
                pod_name = pod.metadata.name
                cluster_name = self._get_cluster_name(secret_data)

                ##################################
                # 2. Make Base Data
                ##################################
                # key:value type data need to be processed separately
                raw_data = pod.to_dict()
                raw_data['metadata']['annotations'] = self._convert_annotations(pod.to_dict())
                raw_data['metadata']['labels'] = self._convert_labels(pod.to_dict())
                raw_data['spec']['node_selector'] = self._convert_node_selector(pod.to_dict())
                raw_data['uid'] = raw_data['metadata']['uid']

                pod_data = Pod(raw_data, strict=False)
                _LOGGER.debug(f'pod_data => {pod_data.to_primitive()}')

                ##################################
                # 3. Make Return Resource
                ##################################
                pod_resource = PodResource({
                    'name': pod_name,
                    'account': cluster_name,
                    'region_code': 'global',
                    'data': pod_data,
                    'reference': pod_data.reference()
                })

                ##################################
                # 4. Make Collected Region Code
                ##################################
                self.set_region_code('global')

                ##################################
                # 5. Make Resource Response Object
                # List of InstanceResponse Object
                ##################################
                collected_cloud_services.append(PodResponse({'resource': pod_resource}))

            except Exception as e:
                _LOGGER.error(f'[collect_cloud_service] => {e}', exc_info=True)
                # Pod name is key
                error_response = self.generate_resource_error_response(e, 'WorkLoad', 'Pod', pod_name)
                error_responses.append(error_response)

        return collected_cloud_services, error_responses

    def _convert_annotations(self, dict_pod):
        """
        Convert annatations to dict => list of dict
        :param dict_annotations:
        :return:
        """
        dict_annotations = dict_pod.get('metadata', {}).get('annotations', {})
        if dict_annotations is not None:
            return self.convert_labels_format(dict_annotations)
        else:
            return []

    def _convert_labels(self, dict_pod):
        """
        Convert labels to dict => list of dict
        :param dict_pod:
        :return:
        """
        dict_labels = dict_pod.get('metadata', {}).get('labels', {})
        if dict_labels is not None:
            return self.convert_labels_format(dict_labels)
        else:
            return []

    def _convert_node_selector(self, dict_pod):
        dict_node_selector = dict_pod.get('spec', {}).get('node_selector', {})
        _LOGGER.debug(f'dict_node_selector => {dict_node_selector}')
        if dict_node_selector is not None:
            return self.convert_labels_format(dict_node_selector)
        else:
            return []

    @staticmethod
    def _get_cluster_name(secret_data):
        """
        Get cluster name from secret_data(kubeconfig)
        :param secret_data:
        :return:
        """
        cluster_name = ''
        current_context = secret_data.get('current-context', '')
        list_contexts = secret_data.get('contexts', [])

        for context in list_contexts:
            if current_context == context.get('name', ''):
                cluster_name = context.get('context', {}).get('cluster', '')

        return cluster_name


