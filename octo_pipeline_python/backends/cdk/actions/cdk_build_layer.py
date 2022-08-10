import os
import sys
from typing import Optional

from overrides import overrides

from octo_pipeline_python.backends.backend import Backend
from octo_pipeline_python.backends.backends_context import BackendsContext
from octo_pipeline_python.backends.cdk.actions.cdk_build import CDKBuild
from octo_pipeline_python.backends.cdk.models import CDKModel
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext


class CDKBuildLayer(CDKBuild):
    @overrides
    def prepare(self, backend: Backend,
                backends_context: BackendsContext,
                pipeline_context: PipelineContext,
                workspace_context: WorkspaceContext,
                action_name: Optional[str]) -> bool:
        super().prepare(backend,
                        backends_context,
                        pipeline_context,
                        workspace_context,
                        action_name)
        cdk_args: CDKModel = backend.backend_args(backends_context,
                                                  pipeline_context,
                                                  workspace_context,
                                                  self.action_type,
                                                  action_name)
        cdk_working_dir = backends_context.attribute(backend.backend_name(),
                                                     "cdk_working_dir", tag=pipeline_context.name)
        layer_folder_structure = cdk_args.layer_folder_structure or \
                                 os.path.join("python", "lib",
                                              f"python{sys.version_info[0]}.{sys.version_info[1]}",
                                              "site-packages")
        cdk_layer_dir = os.path.join(cdk_working_dir, ".build", action_name or "layer", layer_folder_structure)
        backends_context.add_attribute(backend.backend_name(),
                                       "cdk_build_dir", cdk_layer_dir, tag=pipeline_context.name)
        return True
