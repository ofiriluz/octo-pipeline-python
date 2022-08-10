import os
from typing import Dict, Optional

import dotenv

from octo_pipeline_python.backends.cdk.models.cdk_model import CDKDeployEnv
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext


class CDKEnv:
    @staticmethod
    def load_dotenv(pipeline_context: PipelineContext,
                    deploy_env: Optional[CDKDeployEnv] = None,
                    deployment_env_vars: Optional[Dict[str, str]] = None):
        dot_env_file = f'{pipeline_context.source_dir}/.env'
        env_vars = {}
        if os.path.exists(dot_env_file):
            env_vars = dotenv.dotenv_values(dot_env_file)
        if deployment_env_vars:
            env_vars.update(deployment_env_vars)
        if deploy_env:
            env_vars['DEPLOY_ENV'] = deploy_env.value
        env_vars['PROJECT_DIR'] = pipeline_context.source_dir
        with open(dot_env_file, 'w') as file:
            lines = [f'{key}={value}{os.linesep}' for key, value in env_vars.items()]
            file.writelines(lines)
        dotenv.load_dotenv(dotenv_path=dot_env_file)
