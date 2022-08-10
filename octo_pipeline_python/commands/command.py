import argparse
from abc import abstractmethod

from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.backends.backend import BackendsContext
from octo_pipeline_python.workspace.workspace import Workspace


class Command:
    def __init__(self, workspace: Workspace, backends_context: BackendsContext):
        self.workspace: Workspace = workspace
        self.backends_context: BackendsContext = backends_context

    @abstractmethod
    def define_command(self, subparsers) -> None:
        pass

    @abstractmethod
    def run_command(self, args: argparse.Namespace) -> ActionResultCode:
        pass

    @abstractmethod
    def can_run_command(self, command_name: str,
                        args: argparse.Namespace) -> bool:
        pass
