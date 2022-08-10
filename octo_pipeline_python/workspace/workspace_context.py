import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.common.surrounding import Surrounding


class WorkspaceStats(BaseModel):
    init_time: Optional[datetime] = Field(description="Start time of the pipeline")
    pipelines_executed: Optional[int] = Field(description="Number of pipelines executed so far", default=0)


class WorkspaceContext(BaseModel):
    name: str = Field(description="Name of the workspace")
    scm: str = Field(description="Base SCM to grab code from")
    source_dir: str = Field(description="Workspace source directory")
    working_dir: str = Field(description="Workspace working directory")
    surrounding: Surrounding = Field(description="Workspace surrounding")
    organizations: List[str] = Field(description="List of organizations to try and grab the workspace from")
    backends_settings: Optional[Dict[str, "BackendSettings"]] = \
        Field(description="Arguments of the workspace for the backends")
    settings_path: Optional[str] = Field(description="Settings path found for edit")
    stats: WorkspaceStats = Field(description="Stats on the workspace level")
    is_singular: bool = Field(description="Whether this is a singular pipeline and not a workspace", default=False)
    extra_args: Optional[List[str]] = Field(description="Extra command line arguments")

    def backend_args_for_backend(self, backend: "Backend",
                                 workspace_context: "WorkspaceContext") -> Any:
        """
        Getter for the fitting backend args model per workspace
        :param backend:
        :param workspace_context:
        :return:
        """
        from octo_pipeline_python.backends.backend_description import \
            BackendDescription
        backend_desc: BackendDescription = backend.describe_backend(self, workspace_context)
        if self.backends_settings:
            if backend.backend_name() in self.backends_settings and \
                    self.backends_settings[backend.backend_name()].backend_args:
                return backend_desc.backend_model.parse_obj(self.backends_settings[backend.backend_name()].backend_args)
        return None

    def backend_action_settings_for_backend(self, backend: "Backend", action_type: "ActionType",
                                            action_name: Optional[str] = None) -> Dict[str, str]:
        """
        Getter for the settings of the backend per workspace
        :param backend:
        :param action_type:
        :param action_name:
        :return:
        """
        from octo_pipeline_python.backends.backend_settings import \
            ActionSettings
        if self.backends_settings and backend.backend_name() in self.backends_settings:
            if self.backends_settings[backend.backend_name()].backend_action_settings and \
                    ((action_type in self.backends_settings[backend.backend_name()].backend_action_settings) or
                     (action_name and action_name in self.backends_settings[backend.backend_name()].backend_action_settings)):
                action_combined_settings = {}
                action_settings: List[ActionSettings] = []
                if action_type and action_type in self.backends_settings[backend.backend_name()].backend_action_settings:
                    action_settings = self.backends_settings[backend.backend_name()].backend_action_settings[action_type]
                if action_name and action_name in self.backends_settings[backend.backend_name()].backend_action_settings:
                    action_settings = self.backends_settings[backend.backend_name()].backend_action_settings[action_name]
                for setting in action_settings:
                    if not setting.platform or setting.platform == sys.platform:
                        action_combined_settings.update(setting.settings)
                return action_combined_settings
        return {}


# Workaround for circular import of backend settings
from octo_pipeline_python.backends.backend_settings import BackendSettings

WorkspaceContext.update_forward_refs()
