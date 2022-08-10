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


class PyTestUnitTests(Action):
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        ut_dir = os.path.join(pipeline_context.working_dir, backend.backend_name(), "unittests")
        if not os.path.exists(ut_dir):
            os.makedirs(ut_dir)
        backends_context.add_attribute(backend.backend_name(), "ut_dir", ut_dir, tag=pipeline_context.name)
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
        ut_dir = backends_context.attribute(backend.backend_name(), "ut_dir", tag=pipeline_context.name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running unit tests action")
        command = f"{ExecUtils.detect_python()} -m pytest -o cache_dir={ut_dir}/.pytest_cache"
        if pytest_args.verbose:
            command += " -v"
        if pytest_args.xml_report:
            command += f" --junitxml={ut_dir}/unit-test-results.xml"
        if pytest_args.html_report:
            command += f" --html={ut_dir}/unit-tests-report.html --self-contained-html"
        if pytest_args.cov_config:
            command += f" --cov=. --cov-report=html:{ut_dir}/reports/htmlcov"
        command += f" {pytest_args.unit_tests_entry_point}"
        p = pipeline_context.run_contextual(command)
        p.communicate()
        if p.returncode != 0:
            return ActionResult(action_type=self.action_type,
                                result=["Failed running pytest unit tests"],
                                result_code=ActionResultCode.FAILURE)
        return ActionResult(action_type=self.action_type,
                            result=[],
                            result_code=ActionResultCode.SUCCESS)

    def cleanup(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> None:
        ut_dir = backends_context.attribute(backend.backend_name(), "ut_dir", tag=pipeline_context.name)
        if os.path.exists(ut_dir):
            shutil.rmtree(ut_dir)
        return None

    @property
    def action_type(self) -> ActionType:
        return ActionType.UnitTests
