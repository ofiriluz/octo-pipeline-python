from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from octo_pipeline_python.backends.conan.models.conan_configuration import \
    ConanConfiguration


class ConanModel(BaseModel):
    artifactory: Optional[str] = Field(description="Artifactory URL", default="https://conan.io/center/")
    remotes: Optional[List[str]] = Field(default=None, description="List of remotes to use")
    configurations: Optional[List[ConanConfiguration]] = Field(default=None, description="List of configurations to use")
    settings: Optional[Dict[str, Dict[str, str]]] = Field(default=None, description="Key value conan profile settings")
    deploy: Optional[str] = Field(default=None, description="Remote to deploy to")
    no_default_remotes: bool = Field(description="Remove conan default remotes", default=False)
    enable_dependency_collision: bool = Field(description="Allow on dependencies version collisions", default=False)
