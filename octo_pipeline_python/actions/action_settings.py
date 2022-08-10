from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ActionSettings(BaseModel):
    platform: Optional[str] = Field(description="Optional platform filtering")
    settings: Dict[str, Any] = Field(description="Settings for the action")
