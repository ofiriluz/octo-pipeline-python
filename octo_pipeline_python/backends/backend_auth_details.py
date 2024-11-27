from typing import Optional

from pydantic import BaseModel, Field, SecretStr


class BackendAuthDetails(BaseModel):
    username: Optional[str] = Field(default=None, description="Username to authenticate with")
    secret: Optional[SecretStr] = Field(default=None, description="Secret to authenticate with")
    target: Optional[str] = Field(default=None, description="Target to authenticate to")
    certificate: Optional[str] = Field(default=None, description="Certificate to use for authentication")
