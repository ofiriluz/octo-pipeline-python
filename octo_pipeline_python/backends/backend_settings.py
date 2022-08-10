import os
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml
from pydantic import BaseModel, Field, parse_obj_as

from octo_pipeline_python.actions.action_settings import ActionSettings
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.utils.search import PIPELINE_FOLDER, Search

SETTINGS_FILE_NAME = "settings.yml"


class BackendSettings(BaseModel):
    backend_args: Optional[Any] = Field(description="Arguments of the context")
    backend_action_settings: Optional[Dict[Union[ActionType, str], List[ActionSettings]]] = \
        Field(description="Map of action configurations for the backend")

    @staticmethod
    def create(source_dir: str,
               settings_file_path: str = None,
               base_yaml: Dict = None) -> Optional[Tuple[Dict[str, "BackendSettings"], str]]:
        """
        Tries to find and create the settings for the backends
        this is using either settings.yml or settings portion in the base yaml given
        :param source_dir:
        :param settings_file_path:
        :param base_yaml:
        :return:
        """
        settings_yaml = None
        # Get the backends args
        if not settings_file_path:
            # Try to find backends file
            settings_file_path = Search.search_by_name(SETTINGS_FILE_NAME, extra_search_paths=[source_dir])
        if settings_file_path and os.path.exists(settings_file_path):
            with open(settings_file_path, 'r') as settings_file:
                settings_yaml = yaml.load(settings_file, Loader=yaml.FullLoader)
        # If file doesnt exist but there are args in the actual pipeline file, use them
        elif base_yaml and "settings" in base_yaml:
            settings_yaml = base_yaml["settings"]
        if settings_yaml:
            settings: Dict[str, "BackendSettings"] = {}
            for backend in settings_yaml:
                if 'actions' in settings_yaml[backend]:
                    actions = {ActionType._value2member_map_[action] if action in ActionType._value2member_map_.keys() else action:
                                   parse_obj_as(List[ActionSettings], action_settings)
                               for action, action_settings in settings_yaml[backend]['actions'].items()}
                    backend_settings = settings_yaml[backend]
                    del backend_settings['actions']
                    settings[backend] = BackendSettings(backend_args=backend_settings,
                                                        backend_action_settings=actions)
                else:
                    settings[backend] = BackendSettings(backend_args=settings_yaml[backend],
                                                        backend_action_settings=None)
            return settings, settings_file_path
        return {}, settings_file_path

    @staticmethod
    def set_setting(pipeline_context: "PipelineContext",
                    backends_context: "BackendsContext",
                    workspace_context: "WorkspaceContext",
                    backend: str,
                    key: str,
                    value: Any) -> bool:
        from backends.backends_context import BackendsContext
        from pipeline.pipeline_context import PipelineContext
        from workspace.workspace_context import WorkspaceContext
        settings_path = pipeline_context.settings_path
        if not settings_path:
            settings_path = Search.search_by_name(SETTINGS_FILE_NAME, extra_search_paths=[pipeline_context.source_dir])
        if not settings_path:
            settings_path = os.path.join(pipeline_context.source_dir, PIPELINE_FOLDER, SETTINGS_FILE_NAME)
        settings: Dict[str, "BackendSettings"] = pipeline_context.backends_settings
        if not os.path.exists(settings_path):
            if not os.path.exists(os.path.dirname(settings_path)):
                os.makedirs(os.path.dirname(settings_path))
        backend_description = backends_context.describe_backend(backend, workspace_context)
        backend_model = {}
        if backend in settings:
            backend_model = backend_description.backend_model.parse_obj(settings[backend].backend_args).dict()
        else:
            settings[backend] = BackendSettings()
        if key in backend_model and isinstance(backend_model[key], list):
            backend_model[key] = str(value).split(",")
        else:
            backend_model[key] = value
        settings[backend].backend_args = backend_model
        if os.path.exists(settings_path):
            with open(settings_path, 'r+') as settings_file:
                settings_yaml = yaml.load(settings_file, Loader=yaml.FullLoader)
                if backend not in settings_yaml:
                    settings_yaml[backend] = {}
                settings_yaml[backend][key] = backend_model[key]
                settings_file.seek(0)
                settings_file.truncate()
                yaml.dump(settings_yaml, settings_file, default_flow_style=False)
        else:
            with open(settings_path, 'w') as settings_file:
                settings_yaml = {}
                for backend in settings:
                    settings_yaml[backend] = settings[backend].backend_args
                    if settings[backend].backend_action_settings:
                        settings_yaml[backend]["actions"] = settings[backend].backend_action_settings
                yaml.dump(settings_yaml, settings_file, default_flow_style=False)
        return True

    @staticmethod
    def get_setting(pipeline_context: "PipelineContext",
                    backends_context: "BackendsContext",
                    workspace_context: "WorkspaceContext",
                    backend: str,
                    key: str) -> Optional[Any]:
        from backends.backends_context import BackendsContext
        from pipeline.pipeline_context import PipelineContext
        from workspace.workspace_context import WorkspaceContext
        settings: Dict[str, "BackendSettings"] = pipeline_context.backends_settings
        if backend in settings:
            backend_description = backends_context.describe_backend(backend, workspace_context)
            backend_model = {}
            if backend in settings:
                backend_model = backend_description.backend_model.parse_obj(settings[backend].backend_args).dict()
            if key in backend_model:
                return backend_model[key]
        return None
