import os
import platform
import subprocess
from shutil import which
from typing import List


class PackageFinder:
    @staticmethod
    def find_package(name: str,
                     extra_hints: List[str] = None,
                     default: str = "") -> str:
        hints = []
        if extra_hints:
            hints.extend(extra_hints)
        if platform.system() == "Darwin":
            hints.extend(["/usr/local/Cellar", "/usr/local/opt",
                          os.path.join(os.path.expanduser("~"), "brew"),
                          os.path.join(os.path.expanduser("~"), "brew", "opt")])
            if which("brew") is not None:
                # Try finding by brew
                p = subprocess.Popen(f"brew --prefix {name}",
                                     shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                p.wait()
                if p.returncode == 0 and p.stdout:
                    out = p.stdout.read().strip()
                    if out and os.path.exists(out):
                        return out.decode("utf8")
        elif platform.system() == "Linux":
            hints.extend(["/usr/lib/x86_64-linux-gnu", "/usr", "/usr/local"])
        # Try pkg-config
        if which("pkg-config") is not None:
            # Try finding by pkg-config
            p = subprocess.Popen(f"pkg-config --variable=prefix {name}",
                                 shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            p.wait()
            if p.returncode == 0 and p.stdout:
                out = p.stdout.read().strip()
                if out:
                    return out.decode("utf8")
        if name == "qt5" and which("qtchooser") is not None:
            # Try finding specific for qt
            p = subprocess.Popen(f"qtchooser -print-env", shell=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p.wait()
            if p.returncode == 0 and p.stdout:
                out_lines = p.stdout.read().strip().split()
                if out_lines:
                    for line in out_lines:
                        if "QTLIBDIR" in str(line):
                            path = str(line).split("=")[1].replace("\"", "").replace("'", "")
                            if os.path.exists(path):
                                return path
        # Try by extra paths
        for path in hints:
            if os.path.exists(os.path.join(path, name)):
                return os.path.join(path, name)
            if os.path.exists(os.path.join(path, "include", name)):
                return path
            if os.path.exists(os.path.join(path, "lib", name)):
                return path
        return default
