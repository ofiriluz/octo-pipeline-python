from typing import List

from pydantic import BaseModel, Field


class SetupToolsModel(BaseModel):
    packages: List[str] = Field(description="List of packages to pack")
