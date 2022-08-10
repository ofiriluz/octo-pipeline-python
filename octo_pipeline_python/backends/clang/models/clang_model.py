from typing import Optional

from pydantic import BaseModel, Field


class ClangModel(BaseModel):
    fail_diff_count: Optional[int] = Field(description="Amount of diffs to fail on", default=10)
