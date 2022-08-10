import json
import os
from collections import Counter
from shlex import quote
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.snyk.models.snyk_model import SnykModel, Vul
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class SnykSecurityChecks(Action):
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
        snyk_args: SnykModel = backend.backend_args(backends_context,
                                                    pipeline_context,
                                                    workspace_context,
                                                    self.action_type,
                                                    action_name)
        snyk_dir = backends_context.attribute(backend.backend_name(), "snyk_dir",
                                              tag=pipeline_context.name)
        snyk_scan_dir = snyk_args.snyk_scan_dir if snyk_args.snyk_scan_dir else pipeline_context.source_dir
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running security checks action on scan dir [{snyk_scan_dir}]")
        snyk_cmd = f"snyk test --json --json-file-output={quote(snyk_dir + '/snyk_test_scan.json')}"
        if snyk_args.skip_unresolved:
            snyk_cmd += " --skip-unresolved=true"
        if snyk_args.debug:
            snyk_cmd += " --debug"
        else:
            snyk_cmd += " --quiet"
        if snyk_args.fail_on:
            snyk_cmd += f" --fail-on={snyk_args.fail_on}"
        if snyk_args.policy_path:
            snyk_cmd += f" --policy-path={snyk_args.policy_path}"
        p = pipeline_context.run_contextual(snyk_cmd,
                                            cwd=snyk_scan_dir)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed to run snyk test"],
                                result_code=ActionResultCode.FAILURE)
        if os.path.exists(f"{snyk_dir}/snyk_test_scan.json"):
            snyk_scan = None
            with open(f"{snyk_dir}/snyk_test_scan.json", "r") as fh:
                snyk_scan = json.load(fh)
            if 'vulnerabilities' in snyk_scan and isinstance(snyk_scan['vulnerabilities'], list) and \
                    len(snyk_scan['vulnerabilities']) > 0:
                if snyk_args.fail_on and snyk_args.fail_on == "upgradable":
                    snyk_scan['vulnerabilities'] = list(filter(lambda v: v["isUpgradable"], snyk_scan['vulnerabilities']))
                if snyk_args.fail_on and snyk_args.fail_on == "patchable":
                    snyk_scan['vulnerabilities'] = list(filter(lambda v: v["isPatchable"], snyk_scan['vulnerabilities']))
                if len(snyk_scan['vulnerabilities']) > 0:
                    logger.warning(json.dumps(snyk_scan, indent=4))
                    counts = Counter(map(lambda v: v['severity'], snyk_scan['vulnerabilities']))
                    if counts['high'] >= snyk_args.sc_vuls_count[Vul.High] or \
                            counts["medium"] >= snyk_args.sc_vuls_count[Vul.Medium] or \
                            counts["low"] >= snyk_args.sc_vuls_count[Vul.Low]:
                        return ActionResult(action_type=self.action_type,
                                            result=snyk_scan['vulnerabilities'],
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
        return ActionType.SecurityChecks
