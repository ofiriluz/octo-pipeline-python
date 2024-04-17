from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from octo_pipeline_python.backends.conan.models.conan_configuration import \
    ConanConfiguration


class ConanModel(BaseModel):
    artifactory: Optional[str] = Field(description="Artifactory URL", default="https://conan.io/center/")
    remotes: Optional[List[str]] = Field(description="List of remotes to use")
    configurations: Optional[List[ConanConfiguration]] = Field(description="List of configurations to use")
    settings: Optional[Dict[str, Dict[str, str]]] = Field(description="Key value conan profile settings")
    deploy: Optional[str] = Field(description="Remote to deploy to")
    no_default_remotes: bool = Field(description="Remove conan default remotes", default=False)