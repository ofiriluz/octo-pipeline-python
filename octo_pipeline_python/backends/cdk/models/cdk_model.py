from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class CDKDeployEnv(str, Enum):
    Dev = 'dev'
    Test = 'test'
    Stage = 'stage'
    DP = 'dp'
    Integration = 'integration'
    PT = 'pt'
    Prod = 'prod'


class CDKApprovalType(str, Enum):
    Never = "never"
    AnyChange = "any-change"
    Broadening = "broadening"


class CDKIncludePath(BaseModel):
    path: str = Field(description="Path to include")
    envs: Optional[List[CDKDeployEnv]] = Field(description="List of envs to allow this path on")


class CDKModel(BaseModel):
    working_dir: Optional[str] = \
        Field(description="Working directory to work on for the build, defaulted to the pipeline working dir .build")
    skip_deps: bool = Field(description="Whether to skip deps consumption when building / deploying",
                            default=True)
    truncate_deps: Optional[List[str]] = Field(description="Deps paths to ignore when building / deploying")
    development: bool = Field(description="Whether this is a development build and dev deps should also be consumed",
                              default=False)
    verbose: bool = Field(description="Whether to print build / deploy output verbosely",
                          default=False)
    include_paths: Optional[List[Union[str, CDKIncludePath]]] = Field(description="Include paths used for the build")
    exclude_paths: Optional[List[Union[str, CDKIncludePath]]] = Field(description="Excluded paths used for the build, "
                                                                                  "can be exclude patterns from the included paths")
    external_dependencies: Optional[List[str]] = Field(description="Additional external dependencies")
    dev_dependencies: Optional[List[str]] = Field(description="Additional dev dependencies")
    runtime_dependencies: Optional[List[str]] = Field(description="Additional runtime dependencies")
    build_before_deploy: bool = Field(description="Build lambdas before deployment",
                                      default=True)
    clean_before_deploy: bool = Field(description="Clean environment before deployment",
                                      default=False)
    synth_before_deploy: bool = Field(description="Synthesize cloudformation.yml before deploying",
                                      default=True)
    require_approval: CDKApprovalType = Field(description="Approval type before deploying",
                                              default=CDKApprovalType.Broadening)
    deploy_env: CDKDeployEnv = Field(description="Deployment env type",
                                     default=CDKDeployEnv.Dev)
    deployment_env_vars: Optional[Dict[str, str]] = \
        Field(description="Extra environment variables to use while deploying besides dotenv")
    synth_cfn_path: str = Field(
        description="Path to the cloudformation to synth output",
        default="cdk.out/cloudformation.json")
    pre_deploy_script: Optional[str] = Field(
        description="Path to a python script to run prior to deployment")
    post_deploy_script: Optional[str] = Field(
        description="Path to a python script to run after the deployment")
    no_execute: bool = Field(description="Whether to not execute the changeset, only create it",
                             default=False)
    tags: Optional[Dict[str, str]] = Field(description="Tags for the changeset")
    pipenv_path: Optional[str] = Field(description="Path to pipfile lock dir for requirements creation in the cdk build")
    layer_folder_structure: Optional[str] = Field(
        description="Optional folder structure for the layer to put the libs in, "
                    "if not given, deduces it to python/lib/python{major}.{minor}/site-packages")
    strip_exclude_list: Optional[List[str]] = Field(description="List of so files that will not be striped")
