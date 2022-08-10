from typing import List, Optional

from pydantic import BaseModel, Field


class PIPEnvPythonCommandsModel(BaseModel):
    """Model for Execute action."""
    working_dir: Optional[str] = Field(description="Working dir for executing commands")
    python_commands: List[str] = Field(description="List of commands to execute", default_factory=list)
    verbose: bool = Field(description="Execute commands with verbose output to CLI", default=True)
    ignore_failures: bool = Field(description="Ignore non-zero exit codes when executing Python commands",
                                  default=False)


class PIPEnvModel(BaseModel):
    force: bool = Field(description="Whether to force consume without lock file", default=False)
    venv_path: Optional[str] = Field(description="Venv path to activate for")
    pipenv_path: Optional[str] = Field(description="Path to pipenv files")
    system_site_packages: bool = Field(description="Use `--system-site-packages` switch for venv", default=False)
    copy_system_site_packages: bool = Field(description="Use `--copies` switch for venv", default=False)
    python_commands: PIPEnvPythonCommandsModel = Field(default_factory=PIPEnvPythonCommandsModel)
