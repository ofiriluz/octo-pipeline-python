import getpass
import os
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.cdk.actions.cdk_build import CDKBuild
from octo_pipeline_python.backends.cdk.common.cdk_env import CDKEnv
from octo_pipeline_python.backends.cdk.models import CDKModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.git import GitUtils
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class CDKDeploy(Action):
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
        cdk_args: CDKModel = backend.backend_args(backends_context,
                                                  pipeline_context,
                                                  workspace_context,
                                                  self.action_type,
                                                  action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running deploy action in environment [{cdk_args.deploy_env.value}]")
        if cdk_args.build_before_deploy:
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Running build before deploy to update the service")
            builder = CDKBuild()
            if not builder.prepare(backend, backends_context, pipeline_context, workspace_context, action_name):
                return ActionResult(action_type=self.action_type,
                                    result=["Failed to prepare for building environment"],
                                    result_code=ActionResultCode.FAILURE)
            result: ActionResult = builder.execute(backend, backends_context, pipeline_context, workspace_context, action_name)
            if result.result_code != ActionResultCode.SUCCESS:
                return result
        CDKEnv.load_dotenv(pipeline_context, cdk_args.deploy_env, cdk_args.deployment_env_vars)
        # Set the deploy env as env var as well in case the dotenv file parsing did not work
        os.environ["DEPLOY_ENV"] = cdk_args.deploy_env.value
        if cdk_args.clean_before_deploy:
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Running destroy before deploy")
            p = pipeline_context.run_contextual("cdk destroy -f", cwd=pipeline_context.source_dir)
            p.communicate()
            if p.returncode != 0:
                return ActionResult(action_type=self.action_type,
                                    result=["Failed to destroy environment"],
                                    result_code=ActionResultCode.FAILURE)
        if cdk_args.synth_before_deploy:
            if not os.path.exists(os.path.dirname(cdk_args.synth_cfn_path)):
                os.makedirs(os.path.dirname(cdk_args.synth_cfn_path))
            logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                        f"Running synth before deploy")
            p = pipeline_context.run_contextual(f"cdk synth --json > {cdk_args.synth_cfn_path}",
                                                cwd=pipeline_context.source_dir)
            p.communicate()
            if p.returncode != 0:
                return ActionResult(action_type=self.action_type,
                                    result=["Failed to synth environment"],
                                    result_code=ActionResultCode.FAILURE)
        if cdk_args.pre_deploy_script:
            if os.path.exists(cdk_args.pre_deploy_script):
                p = pipeline_context.run_contextual(f"python {cdk_args.pre_deploy_script}",
                                                    cwd=pipeline_context.source_dir)
                p.communicate()
                if p.returncode != 0:
                    return ActionResult(action_type=self.action_type,
                                        result=["Pre deploy script failed"],
                                        result_code=ActionResultCode.FAILURE)
            else:
                logger.warning(f"[{pipeline_context.name}][{backend.backend_name()}] "
                               f"Pre deploy script does not exist, ignoring and deploying")
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Deploying the service to environment [{cdk_args.deploy_env.value}]")
        tags_dict = {
            "user": getpass.getuser().lower(),
            "branch": GitUtils.get_head_branch(pipeline_context.source_dir),
            "commit": GitUtils.get_head_commit(pipeline_context.source_dir)
        }
        if cdk_args.tags:
            tags_dict.update(cdk_args.tags)
        tags_str = ' '.join([f"--tags {key}=\"{value}\"" for key, value in tags_dict.items()])
        if cdk_args.no_execute:
            p = pipeline_context.run_contextual(f"cdk deploy --require-approval never --no-execute {tags_str}",
                                                cwd=pipeline_context.source_dir)
        else:
            p = pipeline_context.run_contextual(f"cdk deploy --require-approval {cdk_args.require_approval.value} {tags_str}",
                                                cwd=pipeline_context.source_dir)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed to deploy environment"],
                                result_code=ActionResultCode.FAILURE)
        if cdk_args.post_deploy_script:
            if os.path.exists(cdk_args.post_deploy_script):
                p = pipeline_context.run_contextual(f"python {cdk_args.post_deploy_script}",
                                                    cwd=pipeline_context.source_dir)
                p.communicate()
                if p.returncode != 0:
                    return ActionResult(action_type=self.action_type,
                                        result=["Post deploy script failed"],
                                        result_code=ActionResultCode.FAILURE)
            else:
                logger.warning(f"[{pipeline_context.name}][{backend.backend_name()}] "
                               f"Post deploy script does not exist, ignoring and finishing")
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
        return ActionType.Deploy
