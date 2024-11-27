from typing import List, Optional, Union

from pydantic import BaseModel, Field


class ExtractTarFile(BaseModel):
    path: str = Field()
    extract_to: Optional[str] = Field(default=None)


class TarModel(BaseModel):
    files_to_extract: List[Union[ExtractTarFile, str]] = Field(description="Paths to extract",
                                                               default_factory=list)
    extract_to: Optional[str] = Field(default=None, description="Optional extract to for all files")
    no_filename_folder_level: bool = Field(description="Do not allow an extra level of folder "
                                                       "structure with the tar file name",
                                           default=True)
