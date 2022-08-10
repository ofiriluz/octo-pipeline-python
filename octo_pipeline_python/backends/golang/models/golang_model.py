from typing import Dict, List

from pydantic import BaseModel, Field


class GolangModel(BaseModel):
    go_path: str = Field(default="go")
    golint_path: str = Field(default="golint")
    verbose_unit_tests: bool = Field(default=True)
    coverage_unit_tests: bool = Field(default=True)
    env: Dict[str, str] = Field(default_factory=dict, description="Env vars for go build")
    entrypoints: List[str] = Field(default_factory=list, description="List of entrypoints to build")
