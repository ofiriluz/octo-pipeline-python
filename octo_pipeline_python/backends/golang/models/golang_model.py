from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class GolangEntrypointInfo(BaseModel):
    path: str = Field(description='Path of the entrypoint')
    output_name: Optional[str] = Field(description='Output name of the entrypoint')


class GolangModel(BaseModel):
    go_path: str = Field(default="go")
    linter: Literal['golint', 'golangci-lint'] = Field(default="golangci-lint")
    golint_path: Optional[str] = Field(description='Path to the linter')
    lint_paths: Optional[List[str]] = Field(description='Paths to run the linter on, if not given, runs on all')
    linter_timeout: int = Field(description='Timeout for the linter in minutes, only applies to golangci', default=3)
    verbose_unit_tests: bool = Field(default=True)
    coverage_unit_tests: bool = Field(default=True)
    env: Dict[str, str] = Field(default_factory=dict, description="Env vars for go build")
    entrypoints: List[Union[str, GolangEntrypointInfo]] = Field(default_factory=list, description="List of entrypoints to build")
    mod_path: Optional[str] = Field(description='Mod path to use instead of root dir one if exists')
