from enum import IntEnum
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from octo_pipeline_python.actions.action_type import ActionType


class ActionResultCode(IntEnum):
    SUCCESS = 0,
    FAILURE = 1,
    PARTIAL_SUCCESS = 2,
    ACTION_DOES_NOT_EXIST = 3


class ActionResult(BaseModel):
    action_type: Optional[ActionType] = Field(description="The action type that ran")
    result: List[Any] = Field(description="Results of the action")
    result_code: ActionResultCode = Field(description="Result code of the action")
