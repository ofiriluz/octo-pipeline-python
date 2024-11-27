from typing import List, Optional, Union

from pydantic import BaseModel, Field


class DownloadFile(BaseModel):
    url: str = Field()
    path: Optional[str] = Field(default=None)


class FileModel(BaseModel):
    files_to_download: List[Union[DownloadFile, str]] = Field(description="Download paths",
                                                              default_factory=list)
    path: Optional[str] = Field(default=None, description="Optional path for all files that are download")
