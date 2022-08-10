from typing import List

from pydantic import BaseModel, Field


class VerifyGPGFile(BaseModel):
    path: str = Field()
    pgp_sig_path: str = Field()
    pgp_fingerprint: str = Field()


class GPGModel(BaseModel):
    files_to_verify: List[VerifyGPGFile] = Field(description="Files to verify",
                                                 default_factory=list)
    key_server: str = Field(description="Key server to use",
                            default="hkps://keyserver.ubuntu.com")
