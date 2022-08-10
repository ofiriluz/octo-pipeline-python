from typing import Dict, Optional

from packaging.version import Version

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.blackduck.models import (
    BlackduckModel, BlackduckRiskThresholds)
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class BlackduckVerify(Action):
    @staticmethod
    def __verify_project_version(blackduck_client: "blackduck.Client",
                                 proj: Dict, proj_version_to_verify: str,
                                 blackduck_args: BlackduckModel) -> Optional[BlackduckRiskThresholds]:
        version_to_verify = None
        if proj_version_to_verify.strip() == "latest":
            sorted_versions = sorted(blackduck_client.get_resource('versions', proj),
                                     key=lambda v: Version(v['versionName']), reverse=True)
            if sorted_versions:
                version_to_verify = sorted_versions[0]
        else:
            for version in blackduck_client.get_resource('versions', proj):
                if version['versionName'] == proj_version_to_verify:
                    version_to_verify = version
                    break
        if version_to_verify:
            risk_profile = blackduck_client.get_resource("riskProfile", version_to_verify, False)
            parsable_risk_profile = {}
            for key, val in risk_profile['categories'].items():
                parsable_risk_profile[key.lower()] = {
                    ck.lower(): cv for ck, cv in val.items()
                }
            # Parse the risk profile to a blackduck thresholds class
            risk_profile = BlackduckRiskThresholds.parse_obj(parsable_risk_profile)
            if risk_profile >= blackduck_args.risk_thresholds:
                return risk_profile
        return None

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
        import blackduck
        blackduck_args: BlackduckModel = backend.backend_args(backends_context,
                                                              pipeline_context,
                                                              workspace_context,
                                                              self.action_type,
                                                              action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running verify action")
        blackduck_secret = backend.load_backend_secret(pipeline_context,
                                                       workspace_context,
                                                       pipeline_context.name)
        if not blackduck_secret:
            return ActionResult(action_type=self.action_type,
                                result=[f"Failed to find blackduck api token"],
                                result_code=ActionResultCode.FAILURE)
        if not blackduck_args.blackduck_certificate_validation:
            blackduck_certificate = False
        else:
            blackduck_certificate = blackduck_secret['certificate']
        blackduck_client = blackduck.Client(
            token=blackduck_secret['token'],
            base_url=blackduck_args.blackduck_url,
            verify=blackduck_certificate
        )
        for proj in blackduck_client.get_resource("projects"):
            for proj_to_verify in blackduck_args.projects_to_verify:
                proj_name_to_verify, proj_version_to_verify = proj_to_verify.split('@', 1)
                if blackduck_args.project_group:
                    proj_name_to_verify = f"{blackduck_args.project_group}-{proj_name_to_verify}"
                if proj['name'] == proj_name_to_verify:
                    risk_profile = \
                        BlackduckVerify.__verify_project_version(blackduck_client, proj,
                                                                 proj_version_to_verify,
                                                                 blackduck_args)
                    if risk_profile:
                        return ActionResult(action_type=self.action_type,
                                            result=[f"Risk profile exceeds thresholds for "
                                                    f"[{proj_name_to_verify}@{proj_version_to_verify}]",
                                                    risk_profile.dict()],
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
