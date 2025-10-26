#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup process."""
import json
import os
from io import open
from os import getenv, path
from typing import Any

import toml
from setuptools import find_packages, setup


def get_package_requirements(package: str, version: Any):
    packages = []
    package_name = package
    if isinstance(version, dict):
        if "sys_platform" in version and version["sys_platform"].split()[1].strip() != sys.platform:
            return packages
        if "version" in version and version['version'] != "*":
            package_name = f"{package}{version['version']}"
        if "extras" in version:
            for extra in version["extras"]:
                packages.append(f"{package}[{extra}]")
    else:
        if isinstance(version, str) and version != "*":
            package_name = f"{package}{version}"
    packages.append(package_name)
    return packages


def get_install_requirements():
    try:
        # read my pipfile
        with open('Pipfile', 'r') as fh:
            pipfile = fh.read()
        # parse the toml
        pipfile_toml = toml.loads(pipfile)
    except FileNotFoundError:
        return []
    # if the package's key isn't there then just return an empty
    # list
    try:
        required_packages = pipfile_toml['packages'].items()
    except KeyError:
        return []
    # If a version/range is specified in the Pipfile honor it
    # otherwise just list the package
    packages = []
    for package, version in required_packages:
        packages.extend(get_package_requirements(package, version))
    return packages


def get_version():
    version = open("VERSION", 'r').read().strip()
    build_number = getenv("BUILD_NUMBER", 0)
    branch = getenv("BRANCH_NAME", "")
    full_version = f"{version}"
    if branch != "":
        if branch.startswith("rc"):
            full_version = f"{version}.rc{build_number}"
        elif branch != 'main' and not branch.startswith('release'):
            full_version = f"{version}.dev{build_number}"
    return full_version


def get_backends_exclude():
    excluded_backends = []
    base_dir = os.path.join("octo_pipeline_python", "backends")
    for backend in os.listdir(base_dir):
        backend_path = os.path.join(base_dir, backend)
        if os.path.isdir(backend_path) and "__pycache__" not in backend_path:
            excluded_backends.append(f"*backends.{backend}*")
    return excluded_backends


def get_backends_extras():
    base_dir = os.path.join("octo_pipeline_python", "backends")
    extras = {}
    for backend in os.listdir(base_dir):
        backend_path = os.path.join(base_dir, backend)
        if os.path.isdir(backend_path) and "__pycache__" not in backend_path and "egg-info" not in backend_path:
            extras[backend] = [f"octo-pipeline-backend-{backend.replace('_', '-')}-python"]
    all_backends = list(extras.keys())
    extras["all"] = [f"octo-pipeline-backend-{backend.replace('_', '-')}-python" for backend in all_backends]
    with open(os.path.join("scripts", "backends_requirements.json"), 'r') as f:
        extra_reqs = json.load(f)
    for backend_req, data in extra_reqs.items():
        for tag in data.get("tags", []):
            if tag not in extras.keys():
                extras[tag] = []
            extras[tag].append(f"octo-pipeline-backend-{backend_req.replace('_', '-')}-python")
    return extras


with open(path.join(path.abspath(path.dirname(__file__)), 'README.md'),
          encoding='utf-8') as f:
    long_description = f.read()


setup(
    # Basic project information
    name='octo-pipeline-python',
    version=get_version(),
    # Authorship and online reference
    author='Ofir Iluz',
    author_email='iluzofir@gmail.com',
    url='https://github.com/ofiriluz/octo-pipeline-python',
    # Detailed description
    description='Octo pipeline',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13'
    ],
    # Package configuration
    packages=find_packages(exclude=('tests', *get_backends_exclude(),)),
    include_package_data=True,
    python_requires='>= 3.11',
    install_requires=get_install_requirements(),
    extras_require=get_backends_extras(),
    # Licensing and copyright
    license='MIT',
    entry_points={
        'console_scripts': ['octo=octo_pipeline_python.octo:main'],
    }
)
