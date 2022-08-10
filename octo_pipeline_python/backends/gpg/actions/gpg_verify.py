import os
from http import HTTPStatus
from typing import Final, Optional

import requests

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.gpg.models import GPGModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class GPGVerify(Action):
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
        from gnupg import GPG
        gpg_args: GPGModel = backend.backend_args(backends_context,
                                                  pipeline_context,
                                                  workspace_context,
                                                  self.action_type,
                                                  action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running verify action")
        gpg = GPG()
        for verify in gpg_args.files_to_verify:
            logger.info(f"Receiving key [{verify.pgp_fingerprint}] from keyserver [{gpg_args.key_server}]")
            recv_result = gpg.recv_keys(gpg_args.key_server, verify.pgp_fingerprint)
            if recv_result is None or recv_result.count == 0 or len(recv_result.fingerprints) == 0:
                return ActionResult(action_type=self.action_type,
                                    result=[f"Failed to import pgp fingerprint key [{verify.pgp_fingerprint}]",
                                            recv_result.__dict__],
                                    result_code=ActionResultCode.FAILURE)
            logger.info(f"Verifying [{verify.path}] with sig [{verify.pgp_sig_path}]")
            with open(os.path.join(pipeline_context.source_dir, verify.pgp_sig_path), 'rb') as f:
                verify_result = gpg.verify_file(f, os.path.join(pipeline_context.source_dir, verify.path))
                if verify_result is None or not verify_result.valid:
                    return ActionResult(action_type=self.action_type,
                                        result=[f"Failed to verify path [{verify.path}] with sig [{verify.pgp_sig_path}]",
                                                verify_result.__dict__],
                                        result_code=ActionResultCode.FAILURE)
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
        return ActionType.Verify
