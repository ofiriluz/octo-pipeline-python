from typing import List

from pydantic import BaseModel, Field

from octo_pipeline_python.pipeline.pipeline_action import PipelineAction
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext


class PipelineDescription(BaseModel):
    actions: List[PipelineAction] = Field(description="List of actions of the pipeline")
    context: PipelineContext = Field(description="Context of the pipeline")
