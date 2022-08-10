import inspect
import json
import os
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.cfn_nag.models import CFNNagModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class CFNNagSecurityChecks(Action):
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
        cfn_nag_args: CFNNagModel = backend.backend_args(backends_context,
                                                         pipeline_context,
                                                         workspace_context,
                                                         self.action_type,
                                                         action_name)
        cfn_nag_dir = backends_context.attribute(backend.backend_name(), "cfn_nag_dir",
                                                 tag=pipeline_context.name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running security checks action")
        profile_path = os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))),
                                    "../", "profiles", "default.profile")
        if cfn_nag_args.profile:
            profile_path = cfn_nag_args.profile
        cfn_nag_rules_cmd = f"cfn_nag_rules --profile-path={profile_path}"
        if cfn_nag_args.custom_rules_path:
            cfn_nag_rules_cmd += f" --rule-directory={cfn_nag_args.custom_rules_path}"

        # Create the cfn nag rules
        p = pipeline_context.run_contextual(f"{cfn_nag_rules_cmd} > {cfn_nag_dir}/cfn_nag_enforced_rules.txt",
                                            cwd=pipeline_context.source_dir)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed to generate cfn rules"],
                                result_code=ActionResultCode.FAILURE)

        # Run cfn nag
        cfn_nag_cmd = f"cfn_nag --profile-path={profile_path} --output-format=json"
        if cfn_nag_args.custom_rules_path:
            cfn_nag_cmd += f" --rule-directory={cfn_nag_args.custom_rules_path}"
        cfn_nag_cmd += f" {cfn_nag_args.cfn_path}"
        p = pipeline_context.run_contextual(f"{cfn_nag_cmd} > {cfn_nag_dir}/cfn_nag_template_scan.json",
                                            cwd=pipeline_context.source_dir)
        p.communicate()
        if os.path.exists(f"{cfn_nag_dir}/cfn_nag_template_scan.json"):
            cfn = json.load(open(f"{cfn_nag_dir}/cfn_nag_template_scan.json", 'r'))
            if isinstance(cfn, list) and len(cfn) > 0:
                logger.warning(json.dumps(cfn, indent=4))
                for scan in cfn:
                    if 'file_results' in scan and 'violations' in scan['file_results']:
                        for violation in scan['file_results']['violations']:
                            if violation["type"] == "FAIL":
                                return ActionResult(action_type=self.action_type,
                                                    result=[json.dumps(cfn, indent=4)],
                                                    result_code=ActionResultCode.FAILURE)
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed to run cfn nag scan"],
                                result_code=ActionResultCode.FAILURE)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        cfn_nag_dir = backends_context.attribute(backend.backend_name(), "cfn_nag_dir",
                                                 tag=pipeline_context.name)
        if os.path.exists(f"{cfn_nag_dir}/cfn_nag_template_scan.json"):
            os.remove(f"{cfn_nag_dir}/cfn_nag_template_scan.json")
        if os.path.exists(f"{cfn_nag_dir}/cfn_nag_enforced_rules.txt"):
            os.remove(f"{cfn_nag_dir}/cfn_nag_enforced_rules.txt")

    @property
    def action_type(self) -> ActionType:
        return ActionType.SecurityChecks
