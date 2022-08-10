import os
from typing import Optional

from overrides import overrides

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backend_auth_details import \
    BackendAuthDetails
from octo_pipeline_python.backends.backend_description import \
    BackendDescription
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.blackduck.actions import (BlackduckDetect,
                                                             BlackduckVerify)
from octo_pipeline_python.backends.blackduck.models import BlackduckModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

TAG = "blackduck"


class BlackduckBackend(Backend):
    def __init__(self) -> None:
        self.__actions = {
            ActionType.Detect: BlackduckDetect(),
            ActionType.Verify: BlackduckVerify()
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
        self.store_backend_secret(
            {"token": auth_details.secret.get_secret_value(),
             "certificate": auth_details.certificate},
            pipeline_context,
            workspace_context,
            tag=pipeline_context.name if pipeline_context else None
        )
        return ActionResultCode.SUCCESS

    def describe_backend(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext) -> BackendDescription:
        return BackendDescription(name=TAG,
                                  working_dir=os.path.join(workspace_context.working_dir, TAG),
                                  actions=self.__actions,
                                  backend_model=BlackduckModel)

    @staticmethod
    def backend_name() -> str:
        return TAG

    @overrides
    def initialize_backend_pipeline_action(self,
                                           action_type: ActionType,
                                           backends_context: BackendsContext,
                                           pipeline_context: PipelineContext,
                                           workspace_context: WorkspaceContext,
                                           action_name: Optional[str]) -> bool:
        cppcheck_dir = os.path.join(pipeline_context.working_dir, TAG)
        if not os.path.exists(cppcheck_dir):
            os.makedirs(cppcheck_dir)
        backends_context.add_attribute(TAG, "blackduck_dir", cppcheck_dir, tag=pipeline_context.name)
        return super().initialize_backend_pipeline_action(action_type,
                                                          backends_context,
                                                          pipeline_context,
                                                          workspace_context,
                                                          action_name)

    @overrides
    def cleanup_backend_pipeline_action(self, action_type: ActionType,
                                        backends_context: BackendsContext,
                                        pipeline_context: PipelineContext,
                                        workspace_context: WorkspaceContext,
                                        action_name: Optional[str]) -> None:
        cppcheck_dir = backends_context.attribute(TAG, "blackduck_dir", tag=pipeline_context.name)
        if os.path.exists(cppcheck_dir):
            shutil.rmtree(cppcheck_dir)
        # Delete the secret on cleanup due to it being sensitive
        self.delete_backend_secret(pipeline_context, workspace_context,
                                   pipeline_context.name)
        super().cleanup_backend_pipeline_action(action_type,
                                                backends_context,
                                                pipeline_context,
                                                workspace_context,
                                                action_name)
