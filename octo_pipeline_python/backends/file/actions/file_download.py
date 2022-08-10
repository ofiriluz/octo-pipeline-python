import os
import traceback
from typing import Final, Optional

import requests

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.file.models import FileModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

MAX_CHUNK_SIZE: Final[int] = 8192


class FileDownload(Action):
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
        file_args: FileModel = backend.backend_args(backends_context,
                                                    pipeline_context,
                                                    workspace_context,
                                                    self.action_type,
                                                    action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running download action")
        if not file_args.path:
            file_args.path = "source"
        try:
            for file in file_args.files_to_download:
                if isinstance(file, str):
                    local_path = file_args.path
                    url = file
                else:
                    local_path = file.path or file_args.path
                    url = file.url
                local_path = os.path.join(pipeline_context.source_dir, local_path)
                if os.path.exists(local_path) and not os.path.isdir(local_path):
                    return ActionResult(action_type=self.action_type,
                                        result=[f"Given path [{local_path}] is a file"],
                                        result_code=ActionResultCode.FAILURE)
                else:
                    os.makedirs(local_path, exist_ok=True)
                local_path = os.path.join(local_path, url.split('/')[-1])
                logger.info(f"Downloading [{url}] to [{local_path}]")
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(local_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=MAX_CHUNK_SIZE):
                            f.write(chunk)
            return ActionResult(action_type=self.action_type,
                                result=[],
                                result_code=ActionResultCode.SUCCESS)
        except requests.HTTPError as e:
            return ActionResult(action_type=self.action_type,
                                result=[traceback.format_exc(), str(e)],
                                result_code=ActionResultCode.FAILURE)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        file_args: FileModel = backend.backend_args(backends_context,
                                                    pipeline_context,
                                                    workspace_context,
                                                    self.action_type,
                                                    action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Cleaning download action")
        if not file_args.path:
            file_args.path = pipeline_context.source_dir
        for file in file_args.files_to_download:
            if isinstance(file, str):
                local_path = file_args.path
                url = file
            else:
                local_path = file.path or file_args.path
                url = file.url
            if os.path.exists(local_path) and os.path.isdir(local_path):
                local_path = os.path.join(local_path, url.split('/')[-1])
            if os.path.exists(local_path):
                os.remove(local_path)

    @property
    def action_type(self) -> ActionType:
        return ActionType.Download
