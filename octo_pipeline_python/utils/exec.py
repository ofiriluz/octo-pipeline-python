import shutil
from typing import List, Optional


class ExecUtils:
    @staticmethod
    def detect_exec(possible_names: List[str]) -> Optional[str]:
        for name in possible_names:
            if shutil.which(name) is not None:
                return name
        return None

    @staticmethod
    def detect_python() -> Optional[str]:
        return ExecUtils.detect_exec(["python3", "python3.8", "python"])
