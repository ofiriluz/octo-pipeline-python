import os
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.s3.models import S3Model
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class S3Upload(Action):
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
        import boto3
        s3_args: S3Model = backend.backend_args(backends_context,
                                                pipeline_context,
                                                workspace_context,
                                                self.action_type,
                                                action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running upload action")
        if not s3_args.bucket or not s3_args.folder or not s3_args.files:
            return ActionResult(action_type=self.action_type,
                                result=[f"No bucket, folder or files given"],
                                result_code=ActionResultCode.FAILURE)
        for file in s3_args.files:
            file_full_path = os.path.join(pipeline_context.source_dir, file)
            if not os.path.exists(file_full_path):
                return ActionResult(action_type=self.action_type,
                                    result=[f"File {file_full_path} does not exist"],
                                    result_code=ActionResultCode.FAILURE)
            logger.info(f"Uploading file [{file_full_path}] to [{s3_args.bucket}] [{s3_args.folder}]")
            client = boto3.client("s3")
            client.upload_file(
                Filename=file_full_path,
                Bucket=s3_args.bucket,
                Key=f"{s3_args.folder}/{os.path.basename(file_full_path)}"
            )
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
        return ActionType.Upload
