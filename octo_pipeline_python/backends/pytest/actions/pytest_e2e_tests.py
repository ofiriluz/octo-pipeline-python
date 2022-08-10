import os
import shutil
from typing import Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.pytest.models import PyTestModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.exec import ExecUtils
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class PyTestE2ETests(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        e2e_dir = os.path.join(pipeline_context.working_dir, backend.backend_name(), "e2e_tests")
        if not os.path.exists(e2e_dir):
            os.makedirs(e2e_dir)
        backends_context.add_attribute(backend.backend_name(), "e2e_dir", e2e_dir, tag=pipeline_context.name)
        return True

    def execute(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> ActionResult:
        pytest_args: PyTestModel = backend.backend_args(backends_context,
                                                        pipeline_context,
                                                        workspace_context,
                                                        self.action_type,
                                                        action_name)
        e2e_dir = backends_context.attribute(backend.backend_name(), "e2e_dir", tag=pipeline_context.name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running E2E tests action")
        command = f"{ExecUtils.detect_python()} -m pytest -o cache_dir={e2e_dir}/.pytest_cache"
        if pytest_args.verbose:
            command += " -v"
        if pytest_args.xml_report:
            command += f" --junitxml={e2e_dir}/e2e-test-results.xml"
        if pytest_args.html_report:
            command += f" --html={e2e_dir}/e2e-tests-report.html --self-contained-html"
        if pytest_args.cov_config:
            command += f" --cov=. --cov-report=html:{e2e_dir}/reports/htmlcov --cov-config={pytest_args.cov_config}"
        command += f" {pytest_args.e2e_entry_point}"
        p = pipeline_context.run_contextual(command)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed running pytest E2E tests"],
                                result_code=ActionResultCode.FAILURE)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        e2e_dir = backends_context.attribute(backend.backend_name(), "e2e_dir", tag=pipeline_context.name)
        if os.path.exists(e2e_dir):
            shutil.rmtree(e2e_dir)
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.E2E
