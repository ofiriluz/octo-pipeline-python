from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class Vul(str, Enum):
    High = "high",
    Medium = "medium",
    Low = "low"


class SnykModel(BaseModel):
    sc_vuls_count: Dict[Vul, int] = Field(description="Vuls map to fail the job on for security checks", default={
        Vul.High: 1,
        Vul.Medium: 10,
        Vul.Low: 100
    })
    iac_vuls_count: Dict[Vul, int] = Field(description="Vuls map to fail the job on for iac checks", default={
        Vul.High: 1,
        Vul.Medium: 10,
        Vul.Low: 100
    })
    skip_unresolved: bool = Field(description="Skip unresolved vuls", default=True)
    debug: bool = Field(description="Snyk debug prints", default=False)
    fail_on: str = Field(description="If snyk should fail only on specific things", default="upgradable")
    cfn_path: str = Field(
        description="Path to the cloudformation to scan",
        default="cdk.out/*.template.json")
    snyk_scan_dir: Optional[str] = Field(description="Custom dir to use for the snyk security checks scanning")
    policy_path: Optional[str] = Field(description="Policy path to use for scans")
