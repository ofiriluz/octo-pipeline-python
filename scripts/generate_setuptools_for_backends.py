import json
import os
import subprocess

TEMPLATE_SETUPTOOLS = """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

import os
import distutils.command.build
import distutils.command.bdist
import setuptools.command.egg_info
from setuptools.command.egg_info import manifest_maker


# Override build command
class BuildCommand(distutils.command.build.build):
    def initialize_options(self):
        distutils.command.build.build.initialize_options(self)
        self.build_base = 'backends_build/{backend}'


# Override bdist command
class BdistCommand(distutils.command.bdist.bdist):
    def finalize_options(self):
        distutils.command.bdist.bdist.finalize_options(self)
        self.dist_dir = 'backends_dist/{backend}'


# Override egg_info command
class EggInfoCommand(setuptools.command.egg_info.egg_info):
    def initialize_options(self):
        setuptools.command.egg_info.egg_info.initialize_options(self)
        self.egg_base = 'backends_build/{backend}'
        
    def find_sources(self):
        manifest_filename = os.path.join(self.egg_info, "SOURCES.txt")
        mm = manifest_maker(self.distribution)
        mm.manifest = manifest_filename
        mm.template = '.temp/backends_requirements/{backend}/MANIFEST.in'
        mm.run()
        self.filelist = mm.filelist


packages = find_packages(where='{backend_path}')
packages = ['octo_pipeline_python.backends.{code_backend}.' + p for p in packages]
setup(
    # Basic project information
    cmdclass={{
        'build': BuildCommand,
        'bdist': BdistCommand,
        'egg_info': EggInfoCommand
    }},
    name='octo-pipeline-backend-{backend}-python',
    version='{version}',
    author='Ofir Iluz',
    author_email='iluzofir@gmail.com',
    url='https://github.com/ofiriluz/octo-pipeline-python',
    description='{backend} backend implementation for octo-pipeline',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10'
    ],
    packages=(f"octo_pipeline_python.backends.{code_backend}", *packages),
    include_package_data=True,
    python_requires='>= 3.8',
    install_requires={requirements},
    license='MIT'
)
"""


def get_version(root_dir: str) -> str:
    version = open(os.path.join(root_dir, "VERSION"), 'r').read().strip()
    build_number = os.getenv("BUILD_NUMBER", 0)
    branch = os.getenv("BRANCH_NAME", "")
    full_version = f"{version}"
    if branch != "":
        if branch.startswith("rc"):
            full_version = f"{version}.rc{build_number}"
        elif branch != 'master' and not branch.startswith('release'):
            full_version = f"{version}.dev{build_number}"
    return full_version


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    backends_reqs_dir = os.path.join(root_dir, ".temp", "backends_requirements")
    scripts_dir = os.path.join(root_dir, "scripts")
    backends_path = os.path.join(root_dir, "octo_pipeline_python", "backends")
    version = get_version(root_dir)
    with open(os.path.join(scripts_dir, "backends_requirements.json"), 'r') as f:
        extra_reqs = json.load(f)
    for backend in os.listdir(backends_reqs_dir):
        code_backend = backend.replace("-", "_")
        backend_reqs_path = os.path.join(backends_reqs_dir, backend)
        requirements = []
        if os.path.isdir(backend_reqs_path) and os.path.exists(os.path.join(backend_reqs_path, "requirements.txt")):
            with open(os.path.join(backend_reqs_path, "requirements.txt"), 'r') as f:
                requirements = [r.strip() for r in f.readlines()]
        backend_path = os.path.join(backends_path, code_backend)
        if os.path.exists(backend_path) and os.path.isdir(backend_path):
            formatted_setup = TEMPLATE_SETUPTOOLS.format(
                root_dir=root_dir,
                version=version,
                backend=backend,
                code_backend=code_backend,
                backend_path=backend_path,
                requirements=str(requirements)
            )
            with open(os.path.join(backend_reqs_path, 'setup.py'), 'w') as f:
                f.write(formatted_setup)
            if backend in extra_reqs.keys() and "data" in extra_reqs[backend].keys() and len(extra_reqs[backend]["data"]) > 0:
                with open(os.path.join(backend_reqs_path, 'MANIFEST.in'), 'w') as f:
                    f.write('\n'.join([
                        f"include octo_pipeline_python/backends/{code_backend}/{data}"
                        for data in extra_reqs[backend]["data"]]))
            retcode = subprocess.call(f"python3 {os.path.join('scripts', backend_reqs_path, 'setup.py')} bdist_wheel",
                                      shell=True, cwd=root_dir)
            if retcode != 0:
                print(f"Failed to run dist on backend [{backend}] - [{retcode}]")


if __name__ == "__main__":
    main()
