from typing import Dict, List

from pydantic import BaseModel, Field

from octo_pipeline_python.workspace.workspace_pipeline import WorkspacePipeline


class WorkspaceState(BaseModel):
    unresolved_pipelines: Dict[str, List[WorkspacePipeline]] = Field(
        description="List of pipelines that are not yet resolved in the workspace")
    unsynced_pipelines: Dict[str, List[WorkspacePipeline]] = Field(
        description="List of unsynced pipelines in the workspace")
    synced_pipelines: Dict[str, List[WorkspacePipeline]] = Field(
        description="List of synced pipelines in the workspace")
    completed_pipelines: Dict[str, List[WorkspacePipeline]] = Field(
        description="List of completed pipelines in the workspace")
    read_only_pipelines: Dict[str, List[WorkspacePipeline]] = Field(
        description="List of read only pipelines (not executable) in the workspace")
    failed_pipelines: Dict[str, List[WorkspacePipeline]] = Field(
        description="List of failed pipelines in the workspace")
