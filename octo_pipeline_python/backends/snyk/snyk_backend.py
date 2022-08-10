import os
import shutil
from shlex import quote
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
from octo_pipeline_python.backends.snyk.actions import (SnykCodeChecks,
                                                        SnykIACChecks,
                                                        SnykSecurityChecks)
from octo_pipeline_python.backends.snyk.models import SnykModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

TAG = "snyk"


class SnykBackend(Backend):
    def __init__(self) -> None:
        self.__actions = {
            ActionType.CodeChecks: SnykCodeChecks(),
            ActionType.SecurityChecks: SnykSecurityChecks(),
            ActionType.IACChecks: SnykIACChecks()
        }

    def initialize_backend(self,
                           backends_context: BackendsContext,
                           workspace_context: WorkspaceContext) -> bool:
        return True

    def authenticate_backend(self,
                             auth_details: BackendAuthDetails,
                             backends_context: BackendsContext,
                             workspace_context: WorkspaceContext,
                             pipeline_context: Optional[PipelineContext]) -> ActionResultCode:
        # Authenticate snyk with a given token
        snyk_cmd = f"snyk auth {quote(auth_details.secret.get_secret_value())}"
        p = pipeline_context.run_contextual(snyk_cmd)
        p.communicate()
        if p.returncode == 0:
            return ActionResultCode.SUCCESS
        return ActionResultCode.FAILURE

    def cleanup_backend(self,
                        backends_context: BackendsContext,
                        workspace_context: WorkspaceContext) -> None:
        return None

    def describe_backend(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext) -> BackendDescription:
        return BackendDescription(name=TAG,
                                  working_dir=os.path.join(workspace_context.working_dir, TAG),
                                  actions=self.__actions,
                                  backend_model=SnykModel)

    @overrides
    def initialize_backend_pipeline_action(self,
                                           action_type: ActionType,
                                           backends_context: BackendsContext,
                                           pipeline_context: PipelineContext,
                                           workspace_context: WorkspaceContext,
                                           action_name: Optional[str]) -> bool:
        snyk_dir = os.path.join(pipeline_context.working_dir, TAG)
        if not os.path.exists(snyk_dir):
            os.makedirs(snyk_dir)
        backends_context.add_attribute(TAG, "snyk_dir", snyk_dir, tag=pipeline_context.name)
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
        snyk_dir = backends_context.attribute(TAG, "snyk_dir", tag=pipeline_context.name)
        if os.path.exists(snyk_dir):
            shutil.rmtree(snyk_dir)
        super().cleanup_backend_pipeline_action(action_type,
                                                backends_context,
                                                pipeline_context,
                                                workspace_context,
                                                action_name)

    @staticmethod
    def backend_name() -> str:
        return TAG
