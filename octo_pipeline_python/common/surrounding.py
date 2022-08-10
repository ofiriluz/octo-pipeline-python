from enum import Enum


class Surrounding(str, Enum):
    Jenkins = "jenkins",
    Local = "local",
    OnDemand = "on-demand",
    Workspace = "workspace"
