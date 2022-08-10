from typing import List, Optional

from pydantic import BaseModel, Field

from octo_pipeline_python.actions.action_type import ActionType
from octo_pipeline_python.common.surrounding import Surrounding


class PipelineAction(BaseModel):
    action_type: ActionType = Field(description="Type of action to run")
    backends: List[str] = Field(description="On which backends to run the action")
    surroundings: List[Surrounding] = Field(description="Which surroundings is the action allowed to run on")
    action_name: Optional[str] = Field(description="Action name to make the action unique")
