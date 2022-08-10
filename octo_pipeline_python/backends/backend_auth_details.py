from typing import Optional

from pydantic import BaseModel, Field, SecretStr


class BackendAuthDetails(BaseModel):
    username: Optional[str] = Field(description="Username to authenticate with")
    secret: Optional[SecretStr] = Field(description="Secret to authenticate with")
    target: Optional[str] = Field(description="Target to authenticate to")
    certificate: Optional[str] = Field(description="Certificate to use for authentication")
