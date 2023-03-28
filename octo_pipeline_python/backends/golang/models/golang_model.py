from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class GolangEntrypointInfo(BaseModel):
    path: str = Field(description='Path of the entrypoint')
    output_name: Optional[str] = Field(description='Output name of the entrypoint')


class GolangModel(BaseModel):
    go_path: str = Field(default="go")
    golint_path: str = Field(default="golint")
    verbose_unit_tests: bool = Field(default=True)
    coverage_unit_tests: bool = Field(default=True)
    env: Dict[str, str] = Field(default_factory=dict, description="Env vars for go build")
    entrypoints: List[Union[str, GolangEntrypointInfo]] = Field(default_factory=list, description="List of entrypoints to build")
