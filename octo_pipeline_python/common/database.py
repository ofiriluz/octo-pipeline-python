import os
import pickle
from typing import Any, Dict, Optional

from octo_pipeline_python.utils.logger import logger


class Database:
    def __init__(self, base_path: str, tag: str, prefix: str = ''):
        self.__db_file = os.path.join(base_path, ".cache", f".{prefix}.db")
        self.__database = {}
        self.__tag = tag
        self.__dirty = False
        self.reload()

    def __del__(self):
        if self.__dirty:
            self.flush()

    @property
    def database(self) -> Dict[str, Any]:
        """
        Getter for the database
        :return:
        """
        return self.__database

    @property
    def tag(self):
        """
        Tag of the DB
        :return:
        """
        return self.__tag

    def contains(self, key: str) -> bool:
        """
        Checks if key in database
        :param key:
        :return:
        """
        return key in self.__database

    def set(self, key: str, value: Any):
        """
        Setter for the database without flushing
        :param key:
        :param value:
        :return:
        """
        self.__database[key] = value

    def get(self, key: str) -> Any:
        """
        Getter for an key in database
        :param key:
        :return:
        """
        if self.contains(key):
            return self.__database[key]
        return None

    def commit(self, key: str, value: Any, flush: bool = False) -> None:
        """
        Commits the info to the db file
        :param key:
        :param value:
        :param flush:
        :return:
        """
        self.__database[key] = value
        self.__dirty = True
        if flush:
            self.flush()

    def flush(self) -> None:
        """
        Flushes the database to file
        :return:
        """
        if not os.path.exists(os.path.dirname(self.__db_file)):
            os.makedirs(os.path.dirname(self.__db_file))
        with open(self.__db_file, 'wb') as f:
            pickle.dump(self.__database, f, protocol=pickle.HIGHEST_PROTOCOL)
        self.__dirty = False

    def reset(self) -> None:
        """
        Resets the db file
        :return:
        """
        logger.info(f"[{self.tag}] Resetting database")
        if os.path.exists(self.__db_file):
            os.remove(self.__db_file)
        self.__database = {}
        self.__dirty = True

    def reload(self) -> Optional[Dict[str, Any]]:
        """
        Reloads the workspace db file
        :return:
        """
        if os.path.exists(self.__db_file):
            try:
                with open(self.__db_file, 'rb') as f:
                    self.__database = pickle.load(f)
                    self.__dirty = False
                    return self.__database
            except Exception:
                logger.warning(f"[{self.tag}] Could not load DB file")
        return None
