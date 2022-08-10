from abc import abstractmethod
from typing import Dict, Optional

from octo_pipeline_python.actions.action_result import ActionResult
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class Action:
    def action_settings(self,
                        backend: Backend,
                        pipeline_context: PipelineContext,
                        workspace_context: WorkspaceContext) -> Dict[str, str]:
        action_settings = pipeline_context.backend_action_settings_for_backend(backend, self.action_type)
        if not action_settings:
            action_settings = workspace_context.backend_action_settings_for_backend(backend, self.action_type)
            if not action_settings:
                action_settings = {}
        return action_settings

    @abstractmethod
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        """
        Prepares the action based on the backend
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        pass

    @abstractmethod
    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        """
        Runs the action based on the backend
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        pass

    @abstractmethod
    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        """
        Cleans the action based on the backend
        :param backend:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        pass

    @property
    @abstractmethod
    def action_type(self) -> ActionType:
        """
        Type of the action getter
        :return:
        """
        pass
