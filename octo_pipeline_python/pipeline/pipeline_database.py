from typing import Optional

from overrides import overrides

from octo_pipeline_python.common.database import Database
from octo_pipeline_python.pipeline.pipeline_action import PipelineAction
from octo_pipeline_python.pipeline.pipeline_context import PipelineContext
from octo_pipeline_python.pipeline.pipeline_description import \
    PipelineDescription
from octo_pipeline_python.utils.logger import logger


class PipelineDatabase(Database):
    def __init__(self, context: PipelineContext, pipeline_description: PipelineDescription):
        super().__init__(context.working_dir, context.name, f"{context.name}.pipeline")
        self.__context = context
        self.__description = pipeline_description
        self.__current_step_idx = 0
        self.__dirty = False
        self.__disabled_steps = []
        if self.contains("step"):
            self.__current_step_idx = self.get("step")
        if self.contains("dirty"):
            self.__dirty = self.get("dirty")
        else:
            while (len(self.__description.actions) - 1) > self.__current_step_idx and \
                    self.__context.surrounding not in self.__description.actions[self.__current_step_idx].surroundings:
                self.__current_step_idx += 1
        if self.contains("disabled-steps"):
            self.__disabled_steps = self.get("disabled-steps")

    def mark_dirty(self) -> None:
        """
        Marks the pipeline as dirty
        :return:
        """
        self.__dirty = True
        self.commit("dirty", self.__dirty, False)

    def reset_dirtiness(self) -> None:
        """
        Unmarks the dirtiness of the pipeline
        :return:
        """
        self.__dirty = False
        self.commit("dirty", self.__dirty, False)

    def step_next(self) -> None:
        """
        Move the actions step pointer forward and store it
        :return:
        """
        last_idx = self.__current_step_idx
        while (len(self.__description.actions) - 1) > self.__current_step_idx:
            self.__current_step_idx += 1
            if (len(self.__description.actions) - 1) > self.__current_step_idx and \
                    self.__context.surrounding in self.__description.actions[self.__current_step_idx].surroundings:
                break
            else:
                logger.info(f"[{self.tag}] Skipping step [{self.__current_step_idx}. "
                            f"{self.__description.actions[self.__current_step_idx].action_type}]")
        if last_idx != self.__current_step_idx and \
                self.__context.surrounding in self.__description.actions[self.__current_step_idx].surroundings:
            logger.info(f"[{self.tag}] Advanced to step "
                        f"[{self.__current_step_idx}. "
                        f"{self.__description.actions[self.__current_step_idx].action_type}]")
        elif last_idx == self.__current_step_idx == (len(self.__description.actions) - 1):
            self.__current_step_idx = len(self.__description.actions)
            logger.info(f"[{self.tag}] Reached last step")
        self.commit("step", self.__current_step_idx, False)

    def step_previous(self) -> None:
        """
        Move the action step pointer backwards and store it
        :return:
        """
        last_idx = self.__current_step_idx
        while self.__current_step_idx > 0:
            self.__current_step_idx -= 1
            if self.__context.surrounding in self.__description.actions[self.__current_step_idx].surroundings:
                break
        if last_idx != self.__current_step_idx and \
                self.__context.surrounding in self.__description.actions[self.__current_step_idx].surroundings:
            logger.info(f"[{self.tag}] Advanced to step "
                        f"[{self.__current_step_idx}. "
                        f"{self.__description.actions[self.__current_step_idx].action_type}]")
        else:
            self.__current_step_idx = 0
            logger.info(f"[{self.tag}] Reached first step")
        self.commit("step", self.__current_step_idx, False)

    def disable_step(self,
                     action: str,
                     backend: Optional[str] = None,
                     command: Optional[str] = None) -> None:
        """
        Disables a step and saves it on the DB
        :param action:
        :param backend:
        :param command:
        :return:
        """
        # Check if the step is already disabled
        step_found = False
        for disabled_step in self.__disabled_steps:
            if disabled_step["action"] == action:
                if backend and 'backend' in disabled_step and backend != disabled_step['backend']:
                    continue
                if command and 'command' in disabled_step and command != disabled_step['command']:
                    continue
                logger.info(f"Step [{action}] is already disabled")
                step_found = True
                break
        if not step_found:
            logged_msg = f"Disabling step [{action}]"
            if backend:
                logged_msg += f" for backend [{backend}]"
            if command:
                logged_msg += f" for command [{command}]"
            logger.info(logged_msg)
            disabled_step = {
                "action": action
            }
            if backend:
                disabled_step["backend"] = backend
            if command:
                disabled_step["command"] = command
            self.__disabled_steps.append(disabled_step)
            self.commit("disabled-steps", self.__disabled_steps, True)

    def enable_step(self,
                    action: str,
                    backend: Optional[str] = None,
                    command: Optional[str] = None) -> None:
        for idx, disabled_step in enumerate(self.__disabled_steps):
            if disabled_step["action"] == action:
                if backend and 'backend' in disabled_step and backend != disabled_step['backend']:
                    continue
                if command and 'command' in disabled_step and command != disabled_step['command']:
                    continue
                logged_msg = f"Enabling step [{action}]"
                if backend:
                    logged_msg += f" for backend [{backend}]"
                if command:
                    logged_msg += f" for command [{command}]"
                logger.info(logged_msg)
                del self.__disabled_steps[idx]
                self.commit("disabled-steps", self.__disabled_steps, True)
                break

    def is_step_disabled(self,
                         action: str,
                         backend: Optional[str] = None,
                         command: Optional[str] = None) -> bool:
        for disabled_step in self.__disabled_steps:
            if disabled_step["action"] == action:
                if backend and 'backend' in disabled_step and backend != disabled_step['backend']:
                    continue
                if command and 'command' in disabled_step and command != disabled_step['command']:
                    continue
                return True
        return False

    @overrides
    def reset(self) -> None:
        self.__current_step_idx = 0
        self.__dirty = False
        super().reset()

    @property
    def current_step(self) -> Optional[PipelineAction]:
        """
        Getter for the current step
        :return:
        """
        if self.__current_step_idx < len(self.__description.actions) and \
                self.__context.surrounding in self.__description.actions[self.__current_step_idx].surroundings:
            return self.__description.actions[self.__current_step_idx]
        return None

    @property
    def current_step_idx(self) -> int:
        """
        Getter for the current step index
        :return:
        """
        return self.__current_step_idx

    @property
    def has_steps(self) -> bool:
        """
        Getter for if theres more steps or not
        :return:
        """
        return self.__current_step_idx < len(self.__description.actions)

    @property
    def dirty(self) -> bool:
        """
        Getter for if the pipeline is dirty
        :return:
        """
        return self.__dirty
