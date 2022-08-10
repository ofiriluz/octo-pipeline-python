from typing import Dict, Optional

from pydantic import BaseModel, Field


class DockerModel(BaseModel):
    tag: Optional[str] = Field(description="Output tag of the container")
    args: Optional[Dict[str, str]] = Field(description="Build container args")
    verbose: Optional[bool] = Field(description="Verbosity on docker commands", default=False)
