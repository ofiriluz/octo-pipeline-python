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


class S3Download(Action):
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
                    f"Running download action")
        if not s3_args.bucket or not s3_args.folder or not s3_args.files or not s3_args.download_output_path:
            return ActionResult(action_type=self.action_type,
                                result=[f"No bucket, folder or files given, or where to download them to"],
                                result_code=ActionResultCode.FAILURE)
        os.makedirs(s3_args.download_output_path, exist_ok=True)
        for file in s3_args.files:
            logger.info(f"Downloading file [{file}] from [{s3_args.bucket}] [{s3_args.folder}] "
                        f"to [{s3_args.download_output_path}]")
            client = boto3.client("s3")
            client.download_file(
                Bucket=s3_args.bucket,
                Key=f"{s3_args.folder}/{file}",
                Filename=s3_args.download_output_path
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
        return ActionType.Download
