from collections import namedtuple

from octo_pipeline_python.backends.conan.common.package_finder import \
    PackageFinder
from octo_pipeline_python.backends.conan.common.pattern_finder import \
    PatternFinder

Requirement = namedtuple("Requirement", ("name", "version", "branch"),
                         defaults=("master",))

__ALL__ = [
    "PackageFinder",
    "PatternFinder",
    "Requirement",
]
