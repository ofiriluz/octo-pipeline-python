import glob
import os
import re
import shutil
import tarfile
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.tar.models import TarModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class TarExtract(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        tar_args: TarModel = backend.backend_args(backends_context,
                                                  pipeline_context,
                                                  workspace_context,
                                                  self.action_type,
                                                  action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running extract action")
        if not tar_args.extract_to:
            tar_args.extract_to = "source"
        for file_to_extract in tar_args.files_to_extract:
            if isinstance(file_to_extract, str):
                path = file_to_extract
                extract_to = tar_args.extract_to
            else:
                path = file_to_extract.path
                extract_to = file_to_extract.extract_to or tar_args.extract_to
            extract_to = os.path.join(pipeline_context.source_dir, extract_to)
            for f in glob.glob(path):
                with tarfile.open(f) as tar:
                    logger.info(f"Extracting [{f}] to [{extract_to}]")
                    tar.extractall(extract_to)
                    common_prefix = os.path.commonprefix(tar.getnames())
                    if tar_args.no_filename_folder_level and common_prefix != "":
                        possible_folder_path = os.path.join(extract_to,
                                                            common_prefix)
                        if os.path.exists(possible_folder_path):
                            for file in os.listdir(possible_folder_path):
                                shutil.move(os.path.join(possible_folder_path, file), os.path.join(extract_to, file))
                        os.rmdir(possible_folder_path)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        pass

    @property
    def action_type(self) -> ActionType:
        return ActionType.Extract
