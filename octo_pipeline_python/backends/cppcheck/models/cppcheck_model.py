from typing import List, Optional

from pydantic import BaseModel, Field

IGNORED_FOLDERS = (".git", ".vscode", "build", "install",)


class CppCheckModel(BaseModel):
    fail_count: Optional[int] = Field(description="Amount of errors to fail on",
                                      default=10)
    force: Optional[bool] = Field(description="Force checking of all"
                                              " configurations in files.",
                                  default=False)
    ignore_folders: Optional[List[str]] = Field(
            description="Comma seperated list of folder to ignore.",
            default=list(IGNORED_FOLDERS))
    define_preprocessor_symbols: Optional[List[str]] = Field(
            description="Comma seperated list of preprocessor symbols.")
    include_files: Optional[List[str]] = Field(
            description="Comma seperated list of files to include before check.")
