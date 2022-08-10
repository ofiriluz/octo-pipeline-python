import argparse
import os
import tempfile
from abc import abstractmethod
from datetime import datetime, timedelta
from string import Template
from typing import Any, Dict, Final, Optional

from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.backends.backend_auth_details import \
    BackendAuthDetails
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.backends_keyring import BackendsKeyring
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.utils.pydantic_argparse import PydanticArgparse
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

DEFAULT_KEYRING_EXP_MINUTES: Final[int] = 60


class Backend:
    @abstractmethod
    def initialize_backend(self,
                           backends_context: BackendsContext,
                           workspace_context: WorkspaceContext) -> bool:
        pass

    @abstractmethod
    def cleanup_backend(self,
                        backends_context: BackendsContext,
                        workspace_context: WorkspaceContext) -> None:
        pass

    @abstractmethod
    def authenticate_backend(self, auth_details: BackendAuthDetails,
                             backends_context: BackendsContext,
                             workspace_context: WorkspaceContext,
                             pipeline_context: Optional[PipelineContext]) -> ActionResultCode:
        pass

    @abstractmethod
    def describe_backend(self,
                         backends_context: BackendsContext,
                         workspace_context: WorkspaceContext) -> "BackendDescription":
        pass

    @staticmethod
    @abstractmethod
    def backend_name() -> str:
        pass

    def initialize_backend_pipeline_action(self,
                                           action_type: ActionType,
                                           backends_context: BackendsContext,
                                           pipeline_context: PipelineContext,
                                           workspace_context: WorkspaceContext,
                                           action_name: Optional[str]) -> bool:
        """
        Runs the prepare portion of the action for the pipeline
        :param action_type:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from backends.backend_description import BackendDescription
        description: BackendDescription = self.describe_backend(backends_context, workspace_context)
        if action_type in description.actions:
            action = description.actions[action_type]
            logger.info(f"[{pipeline_context.name}][{self.backend_name()}] "
                        f"Initializing action [{action.action_type}] for backend"
                        + (f" for action name [{action_name}]" if action_name else ""))
            return action.prepare(self, backends_context, pipeline_context, workspace_context, action_name)
        return False

    def execute_backend_pipeline_action(self, action_type: ActionType,
                                        backends_context: BackendsContext,
                                        pipeline_context: PipelineContext,
                                        workspace_context: WorkspaceContext,
                                        action_name: Optional[str]) -> ActionResult:
        """
        Runs the execute portion of the action for the pipeline
        :param action_type:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name:
        :return:
        """
        from backends.backend_description import BackendDescription
        description: BackendDescription = self.describe_backend(backends_context, workspace_context)
        if action_type in description.actions:
            action = description.actions[action_type]
            logger.info(f"[{pipeline_context.name}][{self.backend_name()}] "
                        f"Execution action [{action.action_type}] for backend"
                        + (f" for action name [{action_name}]" if action_name else ""))
            return action.execute(self, backends_context, pipeline_context, workspace_context, action_name)
        return ActionResult(action_type=None,
                            result=[f"Action does not exist for {self.backend_name()}"],
                            result_code=ActionResultCode.ACTION_DOES_NOT_EXIST)

    def cleanup_backend_pipeline_action(self, action_type: ActionType,
                                        backends_context: BackendsContext,
                                        pipeline_context: PipelineContext,
                                        workspace_context: WorkspaceContext,
                                        action_name: Optional[str]) -> None:
        """
        Runs the cleanup portion of the action for the pipeline
        :param action_type:
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_name
        :return:
        """
        from backends.backend_description import BackendDescription
        description: BackendDescription = self.describe_backend(backends_context, workspace_context)
        if action_type in description.actions:
            action = description.actions[action_type]
            logger.info(f"[{pipeline_context.name}][{self.backend_name()}] "
                        f"Cleaning action [{action.action_type}] for backend"
                        + (f" for action name [{action_name}]" if action_name else ""))
            action.cleanup(self, backends_context, pipeline_context, workspace_context, action_name)

    def backend_args(self, backends_context: Optional[BackendsContext],
                     pipeline_context: Optional[PipelineContext],
                     workspace_context: Optional[WorkspaceContext],
                     action_type: Optional[ActionType] = None,
                     action_name: Optional[str] = None) -> Any:
        """
        Tries to retrieve the backend args, either from the pipeline or from the workspace
        :param backends_context:
        :param pipeline_context:
        :param workspace_context:
        :param action_type:
        :param action_name:
        :return:
        """
        args = None
        action_args = None
        model = self.describe_backend(backends_context, workspace_context).backend_model
        if pipeline_context:
            args = pipeline_context.backend_args_for_backend(self, workspace_context)
        if action_type:
            action_args = pipeline_context.backend_action_settings_for_backend(self, action_type, action_name)
        if not args:
            if workspace_context:
                args = workspace_context.backend_args_for_backend(self, workspace_context)
            if not args and workspace_context and backends_context:
                args = self.describe_backend(backends_context, workspace_context).backend_model()
        if action_type and not action_args:
            action_args = workspace_context.backend_action_settings_for_backend(self, action_type, action_name)
        args = args.dict()
        if action_args:
            args.update(action_args)
        if workspace_context and workspace_context.extra_args:
            schema = args.schema()
            parser = argparse.ArgumentParser()
            PydanticArgparse.schema_to_argparse(schema, parser)
            known, unknown = parser.parse_known_args(workspace_context.extra_args)
            args = args.dict()
            args.update(PydanticArgparse.argparse_to_schema(schema, known))
        sub = {
            **os.environ,
            **(pipeline_context.dict() if pipeline_context else {})
        }
        if pipeline_context:
            sub['full_version'] = pipeline_context.full_version
        for key in args.keys():
            if isinstance(args[key], str):
                args[key] = Template(args[key]).safe_substitute(sub)
            elif isinstance(args[key], list):
                for idx in range(len(args[key])):
                    if isinstance(args[key][idx], str):
                        args[key][idx] = Template(args[key][idx]).safe_substitute(sub)
        args = model.parse_obj(args)
        return args

    def store_backend_secret(self, secret: Dict,
                             pipeline_context: Optional[PipelineContext],
                             workspace_context: Optional[WorkspaceContext],
                             expiration_time: Optional[datetime] = None,
                             tag: Optional[str] = None) -> None:
        keyring_path = workspace_context.working_dir if workspace_context \
            else pipeline_context.working_dir if pipeline_context \
            else tempfile.gettempdir()
        if not expiration_time:
            expiration_time = datetime.now() + timedelta(minutes=DEFAULT_KEYRING_EXP_MINUTES)
        keyring = BackendsKeyring(keyring_path)
        keyring.save_secret(self.backend_name(), secret, expiration_time, tag)

    def load_backend_secret(self, pipeline_context: Optional[PipelineContext],
                            workspace_context: Optional[WorkspaceContext],
                            tag: Optional[str] = None) -> Dict:
        keyring_path = workspace_context.working_dir if workspace_context \
            else pipeline_context.working_dir if pipeline_context \
            else tempfile.gettempdir()
        keyring = BackendsKeyring(keyring_path)
        return keyring.load_secret(self.backend_name(), tag)

    def delete_backend_secret(self, pipeline_context: Optional[PipelineContext],
                              workspace_context: Optional[WorkspaceContext],
                              tag: Optional[str] = None):
        keyring_path = workspace_context.working_dir if workspace_context \
            else pipeline_context.working_dir if pipeline_context \
            else tempfile.gettempdir()
        keyring = BackendsKeyring(keyring_path)
        keyring.delete_secret(self.backend_name(), tag)
