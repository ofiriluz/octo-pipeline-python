import os
import subprocess
from typing import Optional

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backend_auth_details import \
    BackendAuthDetails
from octo_pipeline_python.backends.backend_description import \
    BackendDescription
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.golang.actions import (GolangBuild,
                                                          GolangLintChecks,
                                                          GolangUnitTests)
from octo_pipeline_python.backends.golang.models import GolangModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

TAG = "golang"


class GolangBackend(Backend):
    def __init__(self) -> None:
        self.__actions = {
            ActionType.LintChecks: GolangLintChecks(),
            ActionType.UnitTests: GolangUnitTests(),
            ActionType.Build: GolangBuild()
        }

    def initialize_backend(self,
                           backends_context: BackendsContext,
                           workspace_context: WorkspaceContext) -> bool:
        return True

    def cleanup_backend(self,
                        backends_context: BackendsContext,
                        workspace_context: WorkspaceContext) -> None:
        return None

    def authenticate_backend(self,
                             auth_details: BackendAuthDetails,
                             backends_context: BackendsContext,
                             workspace_context: WorkspaceContext,
                             pipeline_context: Optional[PipelineContext]) -> ActionResultCode:
        if auth_details.username and auth_details.secret and auth_details.target:
            logger.info(f"Authenticating to [{auth_details.target}] with [{auth_details.username}]")
            p = subprocess.Popen(f'git config --global '
                                 f'url.https://{auth_details.username}:{auth_details.secret.get_secret_value()}@{auth_details.target}.insteadOf '
                                 f'https://{auth_details.target}', shell=True)
            p.wait()
            if p.returncode != 0:
                logger.warning(f"Failed to authenticate to [{auth_details.target}] with [{auth_details.username}]")
                return ActionResultCode.FAILURE
        else:
            logger.info(f"Not all parameters were given to authenticate")
            return ActionResultCode.FAILURE
        return ActionResultCode.SUCCESS

    def describe_backend(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext) -> BackendDescription:
        return BackendDescription(name=TAG,
                                  working_dir=os.path.join(workspace_context.working_dir, TAG),
                                  actions=self.__actions,
                                  backend_model=GolangModel)

    @staticmethod
    def backend_name() -> str:
        return TAG
