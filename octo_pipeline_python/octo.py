#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# -*- coding: utf-8 -*-

import argparse
import os
import sys
from typing import List

import argcomplete

import octo_pipeline_python.backends.backends
from octo_pipeline_python.actions.action_result import ActionResultCode
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.commands import (BackendsCommand, Command,
                                           PipelineCommand, WorkspaceCommand)
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace import Workspace
from octo_pipeline_python.workspace.workspace_builder import WorkspaceBuilder

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # Create the supported commands list
    # For each command let it define his parsers
    workspace: Workspace = WorkspaceBuilder.create()
    backends_context = None
    if workspace:
        backends_context = BackendsContext(workspace.context)
    commands: List[Command] = [PipelineCommand(workspace, backends_context),
                               BackendsCommand(workspace, backends_context),
                               WorkspaceCommand(workspace, backends_context)]
    for command in commands:
        command.define_command(subparsers)

    argcomplete.autocomplete(parser)
    args, unknown = parser.parse_known_args()
    if len(unknown) > 0:
        workspace.context.extra_args = unknown
    # Run the fitting commands
    for command in commands:
        if command.can_run_command(args.command, args):
            result = command.run_command(args)
            if result == ActionResultCode.SUCCESS:
                sys.exit(0)
            elif result == ActionResultCode.FAILURE:
                logger.error("Failed running command")
                sys.exit(1)
            elif result == ActionResultCode.ACTION_DOES_NOT_EXIST:
                logger.error("No action found")
                sys.exit(1)
            elif result == ActionResultCode.PARTIAL_SUCCESS:
                sys.exit(2)


if __name__ == "__main__":
    main()
