import os
from distutils.util import strtobool
from typing import Dict, Final, Optional

from cachetools import TTLCache, cached

from octo_pipeline_python.backends.cdk.utils.stack_name import get_stack_name


class CDKStack:
    DEPLOY_MASTER_ENV_VAR: Final[str] = "DEPLOY_MASTER"

    @staticmethod
    def is_deploy_to_master() -> bool:
        """
        Checks if the deploy master env var is on, for whether are deploying to master or a dev branch

        :return:
        """
        return strtobool(os.getenv(CDKStack.DEPLOY_MASTER_ENV_VAR, "false"))

    @staticmethod
    @cached(TTLCache(maxsize=10, ttl=600))
    def get_stack_name(base_name: str) -> str:
        """
        Stack name based on master or not

        :return:
        """
        return base_name if \
            CDKStack.is_deploy_to_master() else \
            get_stack_name(base_name)

    @staticmethod
    def stack_outputs(base_name: str, region: Optional[str] = None) -> Dict:
        """
        Loads the stack outputs and returns them

        :param base_name:
        :param region:
        :return:
        """
        import boto3
        target_region = region if region is not None else boto3.session.Session().region_name
        cloudformation = boto3.client('cloudformation', region_name=target_region)

        env = {}
        response = cloudformation.describe_stacks(StackName=CDKStack.get_stack_name(base_name))
        if 'Stacks' in response and response['Stacks'] and 'Outputs' in response['Stacks'][0]:
            for output in response['Stacks'][0]['Outputs']:
                if not str(output['OutputKey']).endswith('ServiceRoleArn'):
                    env[output['OutputKey']] = output['OutputValue']
        return env

    @staticmethod
    def load_env_vars(base_name: str, region: Optional[str] = None) -> Dict:
        """
        Loads the stack outputs and set them as env vars

        :param base_name:
        :param region:
        :return:
        """
        from botocore import xform_name
        stack_outputs = {xform_name(key).upper(): val for key, val in CDKStack.stack_outputs(base_name, region).items()}
        for key, val in stack_outputs.items():
            os.environ[key] = val
        return stack_outputs
