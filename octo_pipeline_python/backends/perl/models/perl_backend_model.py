from typing import List, Optional

from pydantic import BaseModel, Field


class PerlModel(BaseModel):
    perl_commands: List[str] = Field(default_factory=list)
    verbose: bool = Field(default=True)
    ignore_failures: bool = Field(default=False)
    perl_binary_path: str = Field(default="perl")
    working_dir: Optional[str] = Field()
