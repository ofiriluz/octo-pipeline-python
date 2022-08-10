from typing import List, Optional

from pydantic import BaseModel, Field


class S3Model(BaseModel):
    bucket: Optional[str] = Field()
    folder: Optional[str] = Field()
    files: List[str] = Field(default_factory=list)
    download_output_path: Optional[str] = Field()
