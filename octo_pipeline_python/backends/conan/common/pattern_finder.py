import getpass
import os
from typing import Final, List, Optional

from packaging.version import Version

from octo_pipeline_python.pipeline.pipeline import Pipeline
from octo_pipeline_python.utils.logger import logger

DEFAULT_RETRY_COUNT: Final[int] = 3


class PatternFinder:
    @staticmethod
    def __get_recipes_for_result(result) -> List[str]:
        recipes = []
        if result and 'error' in result and not result['error'] and 'results' in result:
            for result_remote in result['results']:
                if 'items' in result_remote:
                    for item in result_remote['items']:
                        if 'recipe' in item and 'id' in item['recipe']:
                            recipes.append(item['recipe']['id'])
        return recipes

    @staticmethod
    def __get_latest_recipe_version(recipes: List[str],
                                    name: str,
                                    version: str,
                                    channel: str,
                                    remote_user: str) -> str:
        latest_version = None
        latest_recipe = None
        for recipe in recipes:
            version = recipe.split('@')[0].split('/')[1]
            if not latest_version or Version(version) > Version(latest_version):
                latest_version = version
                latest_recipe = recipe
        if latest_recipe:
            return latest_recipe
        return f"{name}/{version}+0@{remote_user}/{channel.replace('/', '.')}"

    @staticmethod
    def pattern_for_latest_build_number(name: str,
                                        version: str,
                                        channel: str = "master",
                                        pipeline: Optional[Pipeline] = None,
                                        only_remote: bool = False,
                                        remote_user: str = "prod",
                                        retries: int = DEFAULT_RETRY_COUNT) -> Optional[str]:
        from conans.client import conan_api
        pattern = f"{name}/{version}+0@{remote_user}/{channel.replace('/', '.')}"
        if "OCTO_CONAN_USER_HOME" in os.environ:
            conan_home = os.path.join(os.environ["OCTO_CONAN_USER_HOME"], '.conan')
        elif "CONAN_USER_HOME" in os.environ:
            conan_home = os.path.join(os.environ["CONAN_USER_HOME"], '.conan')
        elif pipeline and os.path.exists(os.path.join(pipeline.context.working_dir, "conan")):
            conan_home = os.path.join(pipeline.context.working_dir, "conan", '.conan')
        else:
            # Cannot deduce conan home
            logger.info(f"Pattern picked for [{name}] => [{pattern}] (1)")
            return pattern
        conan_client: conan_api.Conan = conan_api.Conan(conan_home)
        while retries > 0:
            try:
                # First check if a local package exists
                pattern = f"{name}/{version}+*@{getpass.getuser()}/{channel.replace('/', '.')}"
                if not only_remote:
                    result = conan_client.search_recipes(pattern)
                    local_recipes = PatternFinder.__get_recipes_for_result(result)
                    if len(local_recipes) > 0:
                        pattern = PatternFinder.__get_latest_recipe_version(local_recipes, name, version, channel, remote_user)
                        logger.info(f"Pattern picked for [{name}] => [{pattern}] (2)")
                        return pattern

                # Try the remotes
                pattern = f"{name}/{version}+*@{remote_user}/{channel.replace('/', '.')}"
                remotes = conan_client.remote_list()
                recipes = []
                for remote in remotes:
                    result = conan_client.search_recipes(pattern, remote_name=remote.name)
                    recipes.extend(PatternFinder.__get_recipes_for_result(result))
                if len(recipes) > 0:
                    pattern = PatternFinder.__get_latest_recipe_version(recipes, name, version, channel, remote_user)
                    logger.info(f"Pattern picked for [{name}] => [{pattern}] (3)")
                    return pattern
            except Exception as e:
                logger.warning(f"Error occured while searching for pattern [{str(e)}], Retries left [{retries}]")
            finally:
                retries = retries - 1
        pattern = f"{name}/{version}+0@{remote_user}/{channel.replace('/', '.')}"
        logger.info(f"Pattern picked for [{name}] => [{pattern}] (4)")
        return pattern
