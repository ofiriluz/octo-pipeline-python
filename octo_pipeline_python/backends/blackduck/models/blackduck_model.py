import multiprocessing
from typing import List, Optional

from pydantic import BaseModel, Field


class BlackduckRiskThreshold(BaseModel):
    critical: int = Field(description="Critical risk threshold",
                          default=1)
    high: int = Field(description="High risk threshold",
                      default=1)
    medium: int = Field(description="Medium risk threshold",
                        default=10)
    low: int = Field(description="Low risk threshold",
                     default=50)
    ok: int = Field(description="Ok risk threshold",
                    default=100)
    unknown: int = Field(description="Unknown risk threshold",
                         default=200)

    class Config:
        arbitrary_types_allowed = True

    def __ge__(self, other: "BlackduckRiskThreshold") -> bool:
        return self.critical >= other.critical or \
               self.high >= other.high or \
               self.medium >= other.medium or \
               self.low >= other.low or \
               self.ok >= other.ok or \
               self.unknown >= other.unknown


class BlackduckRiskThresholds(BaseModel):
    activity: BlackduckRiskThreshold = Field(description="Activity risk threshold",
                                             default_factory=BlackduckRiskThreshold)
    license: BlackduckRiskThreshold = Field(description="License risk threshold",
                                            default_factory=BlackduckRiskThreshold)
    operational: BlackduckRiskThreshold = Field(description="Operational risk threshold",
                                                default_factory=BlackduckRiskThreshold)
    version: BlackduckRiskThreshold = Field(description="Version risk threshold",
                                            default_factory=BlackduckRiskThreshold)
    vulnerability: BlackduckRiskThreshold = Field(description="Vulnerability risk threshold",
                                                  default_factory=BlackduckRiskThreshold)

    class Config:
        arbitrary_types_allowed = True

    def __ge__(self, other: "BlackduckRiskThresholds") -> bool:
        return self.activity >= other.activity or \
               self.license >= other.license or \
               self.operational >= other.operational or \
               self.version >= other.version or \
               self.vulnerability >= other.vulnerability


class BlackduckModel(BaseModel):
    # Common params
    blackduck_url: str = Field(description="Blackduck base url")
    blackduck_certificate_validation: bool = Field(description="Whether to validate certificate",
                                                   default=True)
    project_group: Optional[str] = Field(description="Group name of the project, added as part of the project name")

    # Detect params
    detect_script_url = Field(description="Blackduck detect script url to use",
                              default="https://detect.synopsys.com/detect7.sh")
    detect_script_shell = Field(description="Running blackduck detect shell",
                                default="bash")
    parallel_processors: int = Field(description="Amount of parallel detect tasks",
                                     default=min(multiprocessing.cpu_count() / 2, 8))
    detectors: List[str] = Field(description="Detectors to use",
                                 default_factory=list)
    tools: List[str] = Field(description="Scanning tools to use",
                             default_factory=lambda: ["signature_scan", "detector", "impact_analysis"])
    wait_for_results: bool = Field(description="Wait for remote results",
                                   default=True)
    clone_from_latest: bool = Field(description="Whether to clone from latest version if exists and we upgraded a version",
                                    default=True)
    timeout: int = Field(description="Timeout for blackduck detect",
                         default=300)
    excluded_directories: List[str] = Field(description="List of dirs to exclude from scanning",
                                            default_factory=list)
    source_path: Optional[str] = Field(description="Source patch to run the detection on, cwd will be used otherwise")
    code_location_name: Optional[str] = Field(description="Code location name to use")

    # Verify params
    projects_to_verify: List[str] = Field(description="Projects to verify vulnerabilities in format of name@version",
                                          default_factory=list)
    risk_thresholds: BlackduckRiskThresholds = Field(description="Risk thresholds for all types",
                                                     default_factory=BlackduckRiskThresholds)
