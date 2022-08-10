import os
import shutil
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
from octo_pipeline_python.backends.cfn_nag.actions import CFNNagSecurityChecks
from octo_pipeline_python.backends.cfn_nag.models import CFNNagModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

TAG = "cfn-nag"


class CFNNagBackend(Backend):
    def __init__(self) -> None:
        self.__actions = {
            ActionType.SecurityChecks: CFNNagSecurityChecks()
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
        return ActionResultCode.SUCCESS

    def describe_backend(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext) -> BackendDescription:
        return BackendDescription(name=TAG,
                                  working_dir=os.path.join(workspace_context.working_dir, TAG),
                                  actions=self.__actions,
                                  backend_model=CFNNagModel)

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
        cfn_nag_dir = os.path.join(pipeline_context.working_dir, TAG)
        if not os.path.exists(cfn_nag_dir):
            os.makedirs(cfn_nag_dir)
        backends_context.add_attribute(TAG, "cfn_nag_dir", cfn_nag_dir, tag=pipeline_context.name)
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
        cfn_nag_dir = backends_context.attribute(TAG, "cfn_nag_dir", tag=pipeline_context.name)
        if os.path.exists(cfn_nag_dir):
            shutil.rmtree(cfn_nag_dir)
        super().cleanup_backend_pipeline_action(action_type,
                                                backends_context,
                                                pipeline_context,
                                                workspace_context,
                                                action_name)
