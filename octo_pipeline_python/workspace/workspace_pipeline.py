from typing import Tuple

from pydantic import BaseModel, Field


class WorkspacePipeline(BaseModel):
    name: str = Field(description="Name of the pipeline")
    needs: Tuple[str, ...] = Field(description="Other pipelines this pipeline needs to execute")
    head: str = Field(description="Head branch to clone with")
    path: str = Field(description="Path of the workspace pipeline")
    executable: bool = Field(description="Executable pipeline")
    external: bool = Field(description="External to pipeline")

    class Config:
        frozen = True
