import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from packaging.version import Version
from pydantic import BaseModel, Field, validator

from octo_pipeline_python.common.surrounding import Surrounding
from octo_pipeline_python.utils.logger import logger


class PipelineStats(BaseModel):
    start_time: Optional[datetime] = Field(
        description="Start time of the pipeline")
    end_time: Optional[datetime] = Field(description="End time of the pipeline")
    actions_executed: Optional[int] = Field(description="Number of actions executed so far", default=0)


class PipelineContext(BaseModel):
    name: str = Field(description="Name of the context pipeline")
    scm: Union[str, List[str]] = Field(description="SCM of the context")
    version: str = Field(description="Version of the context pipeline")
    build_number: Optional[Union[int, str]] = Field(description="Build number of the pipeline")
    maintainers: Optional[List[str]] = Field(description="List of maintainers")
    head: Optional[str] = Field(description="Branch of the source code context")
    source_dir: str = Field(description="Source directory of the code")
    working_dir: str = Field(description="Working directory of the pipeline")
    surrounding: Surrounding = Field(description="Current running surrounding")
    user: str = Field(description="Current working user, prod if jenkins")
    stats: PipelineStats = Field(description="Stats about the pipeline")
    backends_settings: Optional[Dict[str, "BackendSettings"]] = \
        Field(description="Arguments of the pipeline for the backends")
    settings_path: Optional[str] = Field(
        description="Settings path found for edits")

    @validator("version")
    def version_validator(cls, v):
        """
        Validator for version
        :param v:
        :return:
        """
        try:
            version = Version(v)
            if version:
                return v
        except Exception:
            raise ValueError("Not a version")

    @property
    def full_version(self):
        """
        Concatenates the version and build number
        :return:
        """
        if self.build_number:
            return f"{self.version}+{self.build_number}"
        return self.version

    def backend_args_for_backend(self, backend: "Backend",
                                 workspace_context: "WorkspaceContext") -> Any:
        """
        Getter for the fitting backend args model per pipeline
        :param backend:
        :param workspace_context:
        :return:
        """
        from backends.backend_description import BackendDescription
        backend_desc: BackendDescription = backend.describe_backend(self, workspace_context)
        if backend.backend_name() in self.backends_settings and \
                self.backends_settings[backend.backend_name()].backend_args:
            return backend_desc.backend_model.parse_obj(self.backends_settings[backend.backend_name()].backend_args)
        return None

    def backend_action_settings_for_backend(self, backend: "Backend", action_type: "ActionType",
                                            action_name: Optional[str] = None) -> \
            Optional[Dict[str, str]]:
        """
        Getter for the settings of the backend per pipeline
        :param backend:
        :param action_type:
        :param action_name:
        :return:
        """
        from backends.backend_settings import ActionSettings
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
        return None

    def run_contextual(self, command: str, log_command: bool = True, **kwargs) -> subprocess.Popen:
        runner = ""
        os_pip_path = os.path.join(self.source_dir, "pipenvs", sys.platform)
        if os.path.exists(os.path.join(self.source_dir, "Pipfile")) or os.path.exists(os.path.join(os_pip_path, "Pipfile")):
            try:
                runner = "pipenv run "
                python_path = ""
                env = kwargs.get("env", None) or os.environ.copy()
                env["PIPENV_VENV_IN_PROJECT"] = "1"
                if "VIRTUAL_ENV" not in env:
                    env["VIRTUAL_ENV"] = os.path.join(self.source_dir, ".venv")
                if "PYTHONPATH" in env:
                    python_path = env["PYTHONPATH"]
                venv = os.getenv('VIRTUAL_ENV', None) or env['VIRTUAL_ENV']
                pythondir = next(filter(lambda f: f.startswith("python"), os.listdir(f'{venv}/lib/')))
                env["PYTHONPATH"] = f"{self.source_dir}:{venv}/lib/{pythondir}/site-packages:{python_path}"
                if "SITE_PACKAGES" in os.environ:
                    env["PYTHONPATH"] += f":{os.environ['SITE_PACKAGES']}"
                if os.path.exists(os.path.join(self.source_dir, "Pipfile")):
                    env["PIPENV_PIPFILE"] = os.path.join(self.source_dir, "Pipfile")
                else:
                    env["PIPENV_PIPFILE"] = os.path.join(os_pip_path, "Pipfile")
                kwargs['env'] = env
                logger.info(f"Running with pipenv contexted to [{env['PIPENV_PIPFILE']}]")
            except (StopIteration, FileNotFoundError):
                runner = ""
        if log_command:
            logger.info(f"Running command [{runner}{command}]")
        return subprocess.Popen(f"{runner}{command}", shell=True, **kwargs)


# Workaround for circular import of backend settings
from backends.backend_settings import BackendSettings

PipelineContext.update_forward_refs()
