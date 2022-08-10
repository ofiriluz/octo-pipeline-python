from typing import Optional

from pydantic import BaseModel, Field


class PyTestModel(BaseModel):
    e2e_entry_point: Optional[str] = Field(description="E2e tests code entrypoint",
                                           default="tests/e2e")
    integration_entry_point: Optional[str] = Field(description="Integration tests code entrypoint",
                                                   default="tests/integration")
    unit_tests_entry_point: Optional[str] = Field(description="Unit tests code entrypoint",
                                                  default="tests/unit")
    xml_report: bool = Field(description="Output integration XML result",
                             default=True)
    html_report: bool = Field(description="Output integration HTML result",
                              default=True)
    cov_report: bool = Field(description="Output integration coverage result",
                             default=True)
    cov_config: str = Field(description="Coverage config path",
                            default="tox.ini")
    verbose: bool = Field(description="Verbose test output",
                          default=True)
