import logging
import sys
from typing import Any

import colorama

_default_log_level = \
    logging.DEBUG if "--logger-level-debug" in sys.argv else logging.INFO


class OctoLogger(logging.Logger):
    def __init__(self, name: str, level: int = _default_log_level,
                 verbose: bool = True) -> None:
        self.__verbose = verbose
        super().__init__(name, level)

    @property
    def verbose(self) -> bool:
        return self.__verbose

    def set_verbose(self, verbose: bool) -> None:
        self.__verbose = verbose

    def notice(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if not self.__verbose:
            return
        color_msg = f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}" \
                    f"{msg}{colorama.Style.RESET_ALL}{colorama.Fore.RESET}"
        super().info(f"{color_msg}", *args, **kwargs)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if not self.__verbose:
            return
        color_msg = f"{colorama.Fore.GREEN}" \
                    f"{msg}{colorama.Fore.RESET}"
        super().info(f"{color_msg}", *args, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if not self.__verbose:
            return
        color_msg = f"{colorama.Fore.YELLOW}" \
                    f"{msg}{colorama.Fore.RESET}"
        super().warning(f"{color_msg}", *args, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if not self.__verbose:
            return
        color_msg = f"{colorama.Fore.RED}" \
                    f"{msg}{colorama.Fore.RESET}"
        super().error(f"{color_msg}", *args, **kwargs)

    def fatal(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if not self.__verbose:
            return
        color_msg = f"{colorama.Fore.RED}{colorama.Style.BRIGHT}" \
                    f"{msg}{colorama.Style.RESET_ALL}{colorama.Fore.RESET}"
        super().fatal(f"{color_msg}", *args, **kwargs)
        sys.exit(-1)


def setup_logger() -> logging.Logger:
    log_format = '%(levelname)-8s | %(asctime)s | %(message)s'
    logging.setLoggerClass(OctoLogger)
    logging.basicConfig(format=format(log_format), datefmt="%H:%M:%S %d/%m/%Y",
                        level=_default_log_level)
    return logging.getLogger("octo")


logger = setup_logger()
