import os
import subprocess
import traceback
from typing import List, Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.pipenv.models import PIPEnvModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class PIPEnvExecute(Action):
    __slots__ = (
        "__commands",
        "__ignore_failures",
        "__pipenv_path",
        "__verbose",
        "__working_dir",
    )

    def __init__(self):
        self.__pipenv_path: Optional[str] = None
        self.__working_dir: Optional[str] = None
        self.__verbose: Optional[bool] = None
        self.__ignore_failures: Optional[bool] = None
        self.__commands: Optional[List[str]] = None

    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:

        pipenv_args: PIPEnvModel = backend.backend_args(backends_context, pipeline_context, workspace_context,
                                                        self.action_type, action_name)
        self.__pipenv_path: str = pipeline_context.source_dir
        if pipenv_args.pipenv_path:
            self.__pipenv_path = os.path.normpath(os.path.join(self.__pipenv_path, pipenv_args.pipenv_path))

        self.__working_dir: str = pipeline_context.source_dir
        if pipenv_args.python_commands.working_dir:
            self.__working_dir = \
                os.path.normpath(os.path.join(self.__working_dir, pipenv_args.python_commands.working_dir))
        self.__commands: List[str] = pipenv_args.python_commands.python_commands
        self.__verbose: bool = pipenv_args.python_commands.verbose
        self.__ignore_failures: bool = pipenv_args.python_commands.ignore_failures
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running {self.action_type.value} action with pipenv path [{self.__pipenv_path}]")

        try:
            for python_cmd in self.__commands:
                p = pipeline_context.run_contextual(command=f"python3 {python_cmd}",
                                                    stdout=subprocess.PIPE if not self.__verbose else None,
                                                    stderr=subprocess.PIPE if not self.__verbose else None,
                                                    cwd=self.__working_dir)
                p.communicate()
                if p.returncode != 0:
                    err_str = f"Command [{python_cmd}] failed to finish with rc [{p.returncode}]"
                    if self.__ignore_failures:
                        logger.warning(f"{err_str}, continuing...")
                        continue
                    return ActionResult(action_type=self.action_type,
                                        result=[err_str],
                                        result_code=ActionResultCode.FAILURE)

        except (FileNotFoundError, PermissionError) as e:
            return ActionResult(action_type=self.action_type,
                                result=[traceback.format_exc(), str(e)],
                                result_code=ActionResultCode.FAILURE)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.Execute
