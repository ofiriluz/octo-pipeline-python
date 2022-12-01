from typing import List, Optional

from pydantic import BaseModel, Field


class FilePatch(BaseModel):
    patch_src: str = Field(description="The patch file to apply.")
    patch_dst: str = Field(description="File to apply patch to.")
    platform_list: Optional[List[str]] = Field(description="On what platforms to apply this patch.")


class PatchModel(BaseModel):
    working_dir: Optional[str] = Field(description="Source files location.", default="source")
    files: List[FilePatch] = Field(default_factory=list)
    patch_binary_path: str = Field(default="patch")
    verbose: bool = Field(default=False)
