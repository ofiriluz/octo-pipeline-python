import json
from typing import Dict, Type

from pydantic import BaseModel


class BackendDescription:
    def __init__(self, name: str, working_dir: str, actions: Dict[str, "Action"], backend_model: Type[BaseModel]):
        self.__name = name
        self.__working_dir = working_dir
        self.__actions = actions
        self.__backend_model = backend_model

    @property
    def name(self) -> str:
        return self.__name

    @property
    def working_dir(self):
        return self.__working_dir

    @property
    def actions(self) -> Dict[str, "Action"]:
        return self.__actions

    @property
    def backend_model(self) -> Type[BaseModel]:
        return self.__backend_model

    def __str__(self):
        out = {
            "name": self.name,
            'working_dir': self.working_dir,
            "backend_model": self.backend_model.schema(),
            "supported_actions": list(self.actions.keys())
        }
        return json.dumps(out, indent=4)

    def __repr__(self):
        return self.__str__()
