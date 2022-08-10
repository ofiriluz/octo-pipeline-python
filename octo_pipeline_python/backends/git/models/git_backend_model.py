from typing import Optional

from pydantic import BaseModel, Field


class GitModel(BaseModel):
    head: Optional[str] = Field(description="Head branch or tag", default="master")
    mirror: Optional[str] = Field(description="Mirror remote to add")
    shallow: bool = Field(description="Shallow clone", default=False)
    recursive: bool = Field(description="Recursive clone", default=False)