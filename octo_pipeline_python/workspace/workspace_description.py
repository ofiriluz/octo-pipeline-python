from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from octo_pipeline_python.pipeline.pipeline_description import \
    PipelineDescription
from octo_pipeline_python.workspace.workspace_context import WorkspaceContext
from octo_pipeline_python.workspace.workspace_pipeline import WorkspacePipeline


class WorkspaceDescription(BaseModel):
    workspace: Dict[str, List[WorkspacePipeline]] = Field(description="Workspace description")
    pipelines: Optional[Dict[str, List[PipelineDescription]]] = Field(description="The pipelines in the workspace")
    context: WorkspaceContext = Field(description="Context of the workspace")
