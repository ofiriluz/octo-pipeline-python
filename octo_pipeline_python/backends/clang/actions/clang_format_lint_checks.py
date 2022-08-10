import difflib
import errno
import fnmatch
import io
import json
import os
import subprocess
from typing import Dict, List, Optional

from octo_pipeline_python.actions.action import Action, ActionType
from octo_pipeline_python.actions.action_result import (ActionResult,
                                                        ActionResultCode)
from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.clang.models import ClangModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.utils.logger import logger
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext

DEFAULT_EXTENSIONS = 'c,h,C,H,cpp,hpp,cc,hh,c++,h++,cxx,hxx'
DEFAULT_CLANG_FORMAT_IGNORE = '.clang-format-ignore'


class ClangFormatLintChecks(Action):
    @staticmethod
    def __excludes_from_file() -> List[str]:
        excludes = []
        try:
            with io.open(DEFAULT_CLANG_FORMAT_IGNORE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('#'):
                        # ignore comments
                        continue
                    pattern = line.rstrip()
                    if not pattern:
                        # allow empty lines
                        continue
                    excludes.append(pattern)
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
        return excludes

    @staticmethod
    def __list_files(workspace_path: str) -> List[str]:
        extensions = DEFAULT_EXTENSIONS
        exclude = ClangFormatLintChecks.__excludes_from_file()
        ignore_names = ['.git', 'build', 'install', '.vscode']
        out = []

        for file in os.listdir(workspace_path):
            if file in ignore_names:
                continue
            full_path = os.path.join(workspace_path, file)
            if os.path.isdir(full_path):
                for dirpath, dnames, fnames in os.walk(full_path):
                    fpaths = [os.path.join(dirpath, fname) for fname in fnames]
                    for pattern in exclude:
                        # os.walk() supports trimming down the dnames list
                        # by modifying it in-place,
                        # to avoid unnecessary directory listings.
                        dnames[:] = [
                            x for x in dnames
                            if
                            not fnmatch.fnmatch(os.path.join(dirpath, x).replace(workspace_path, '')[1:], pattern)
                        ]
                        fpaths = [
                            x for x in fpaths if not fnmatch.fnmatch(x, pattern)
                        ]
                    for f in fpaths:
                        ext = os.path.splitext(f)[1][1:]
                        if ext != "" and ext in extensions:
                            out.append(f)
            else:
                ext = os.path.splitext(file)[1][1:]
                if ext != "" and ext in extensions:
                    out.append(full_path)
        return out

    @staticmethod
    def __make_diff(file: str, original: List[str], reformatted: List[str]) -> List[str]:
        return list(difflib.unified_diff(
            original,
            reformatted,
            fromfile=f'{file}(original)',
            tofile=f"{file}(reformatted)",
            n=3))

    @staticmethod
    def __run_clang_format_diff(file: str, pipeline_context: PipelineContext) -> Dict:
        with io.open(file, 'r', encoding='utf-8') as f:
            original = f.readlines()

        proc = pipeline_context.run_contextual(
            f"clang-format --style=file {file}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8')

        # hopefully the stderr pipe won't get full and block the process
        outs = list(proc.stdout.readlines())
        proc.wait()
        return {'diffs': ClangFormatLintChecks.__make_diff(file, original, outs), 'file': file}

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
        clang_args: ClangModel = backend.backend_args(backends_context,
                                                      pipeline_context,
                                                      workspace_context,
                                                      self.action_type,
                                                      action_name)
        logger.info(f"[{pipeline_context.name}][{backend.backend_name()}] "
                    f"Running lint checks action")
        files = self.__list_files(pipeline_context.source_dir)
        diff_files = [self.__run_clang_format_diff(file, pipeline_context) for file in files]
        diffs = []
        for out in diff_files:
            if len(out['diffs']) > 0:
                diffs.append(out)
        if len(diffs) > clang_args.fail_diff_count:
            return ActionResult(action_type=self.action_type,
                                result=[json.dumps(diffs, indent=4)],
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
        return ActionType.LintChecks
