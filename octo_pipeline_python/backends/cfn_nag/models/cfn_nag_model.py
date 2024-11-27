from typing import Optional

from pydantic import BaseModel, Field


class CFNNagModel(BaseModel):
    profile: Optional[str] = Field(
        default=None, description="Profile path to use for cfn nag rules, will use default profile if none specified")
    custom_rules_path: Optional[str] = Field(
        default=None, description="Custom rules folder path for the profile")
    blacklist: Optional[str] = Field(
        default=None, description="Blacklist path to use for cfn scan")
    cfn_path: str = Field(
        description="Path to the cloudformation to scan",
        default="cdk.out/*.template.json")
