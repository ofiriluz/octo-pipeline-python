Octo Pipeline
=================================

[![Octo Build Pipeline](https://github.com/ofiriluz/octo-pipeline-python/actions/workflows/build.yml/badge.svg)](https://github.com/ofiriluz/octo-pipeline-python/actions/workflows/build.yml)


The Octo pipeline gives the ability to work both with an actual pipeline such as jenkins / github actions etc
and locally on a machine

The pipeline consists of the following abbreviations:

- Backend - Some backend that can execute actions
- Action - An action that needs to happen on the backend, such as consume, build
- Pipeline - A set of actions that run on different backends
- Workspace - A set of pipelines with dependencies between them

Each component above can be controlled via the octo executable

Installing
----------

The pipeline requires Python 3.8+

In order to install octo-pipeline, you can install it directly from pypi:

```bash
pip3 install octo-pipeline-python
```

Do notice that we use "extras" for our pipeline, each sub library of the pipeline is a specific backend that you can choose to install or not
Choosing "all" will install the pipeline along with all the backends

```bash
pip3 install install octo-pipeline-python[all]
```

Once the above is done, the pipeline should be installed along with all the dependencies on the machine

You can remove the pip.conf if you don't want to use the index anymore

### Enable AutoComplete

Auto-completion for CLI arguments can be enabled as described in the [argcomplete#zsh-support](https://pypi.org/project/argcomplete/#zsh-support) package which is part of the requirements for octo.

Source the following in your `.bashrc` or `.zshrc`:
```shell
eval "$(register-python-argcomplete octo)"
```


Pipeline Description
--------------------

The pipeline is defined by a yaml file and an optional yaml parameters file

The main pipeline yaml file can look for example as following
```yaml
name: curlpp
scm: https://github.com/jpbarrette/curlpp.git
version: 0.8.1
maintainers:
  - jpbarrette
pipeline:
  - source:
      backend: git
      surroundings:
        - jenkins
        - local
  - consume:
      backend: conan
      surroundings:
        - jenkins
        - local
  - build:
      backend: conan
      surroundings:
        - jenkins
        - local
  - install:
      backend: conan
      surroundings:
        - local
  - package:
      backend: conan
      surroundings:
        - jenkins
        - on-demand
```

This will define a pipeline for the repository, and will run the actions sequential

Each action is defined by a set of backends it needs to run on

Each backend can define the actions it supports accordingly

We can also supply a "name" to the action such that:
```yaml
  - build:
      name: build-win
      backend: golang
      surroundings:
        - jenkins
        - on-demand
  - build:
      name: build-linux
      backend: golang
      surroundings:
        - jenkins
        - on-demand
```
So that we can support multiple actions of the same type for different use cases

Lasty, each action can define on which surroundings it can run on

Currently the supporting surroundings are
- jenkins
- local
- on-demand
- workspace

Along with the above file, you can define parameters for different backends by either specifiying backends key on the pipeline yaml file, or defining a backends.yml file

The backends yaml file can look as follows
```yaml
git:
  head: v0.8.1
conan:
  artifactory: https://jfrog.com
  configurations:
    - debug
    - release
```

For each backend you will define a set of parameters that may or may not be used

If a specific action settings need to apply, or settings for a platform, this can be done as follows:
```yaml
golang:
  actions:
    build-win:
      - platform: linux
        settings:
          env:
            GOOS: windows
            GOARCH: amd64
            GO111MODULE: "on"
            CC: i686-w64-mingw32-gcc
            CXX: i686-w64-mingw32-g++
          entrypoints:
            - cmd/provision_win.go
            - cmd/deprovision_win.go
```

Notice that we can use "build" or "build-win" as action type or action name to define settings for our specific action
Those settings are only applied on the linux platform

Working with the pipeline
-------------------------

Once the pipeline is installed, you can either clone a repository of an existing pipeline and work on ur own

Or u can use the pipeline to help you out

For example, if you wish to work "curlpp" existing pipeline, you could perform the following command
```shell
octo pipeline init --org=pas --name=curlpp
```
The above will try and find inside pas organization the repository, check if it has a pipeline and clone it accordingly

Once the above is done, you can execute the pipeline for that component by running
```shell
octo pipeline execute
```

This will trigger the pipeline defined for the component

You could also run specific actions by running the following
```shell
octo pipeline execute-action consume
```

And lastly, you could run the pipeline step by step and control the flow on ur own

This can be done by using the following commands in a queue style
```shell
octo pipeline step next
octo pipeline step previous
octo pipeline step current
octo pipeline step execute
octo pipeline step clean
octo pipeline step reset
```

All of the above will control each step you are running on

All of the pipeline actions can be listed with --help:
```shell
usage: octo.py pipeline [-h]
                            {init,execute,describe,describe-actions,clean,name,version,build_number,scm,execute-action,clean-action,step}
                            ...

positional arguments:
  {init,execute,describe,describe-actions,clean,name,version,build_number,scm,execute-action,clean-action,step}
    init                Initializes the pipeline backends and working directory
    execute             Executes the entire pipeline actions
    describe            Prints out a detailed description of the pipeline
    describe-actions    Prints out the list of actions on the pipeline
    clean               Cleans up all the actions that ran so far
    name                Prints out the name of the pipeline
    version             Prints out the version of the pipeline
    build_number        Prints out the build number of the pipeline
    scm                 Prints out the scm of the pipeline
    execute-action      Executes a specific type of action
    clean-action        Cleans up a specific type of action
    step                Step execution of the pipeline

optional arguments:
  -h, --help            show this help message and exit
```

Working with a specific backend
-------------------------------

You can execute specific backend operations such as authentication

The backend is responsible for keeping the state of authentication if working via the CLI

If you wish to authenticate to a backend, you may run 
```shell
octo backends conan authenticate --username=john --secret=john --certificate="/path/to/cert"
```

You may also add a target argument if you wish to authenticate to a specific resource in the backend

You may execute other operations on the backed as described in the help

```shell
usage: octo backends conan [-h] {authenticate,describe,working-dir,get} ...

positional arguments:
  {authenticate,describe,working-dir,get}
    authenticate        Authenticate to a backend
    describe            Prints out a description of the backend
    working-dir         Prints out the working directory of the backend
    get                 Gets a specific key from the context of the backend

optional arguments:
  -h, --help            show this help message and exit
```

Working with a workspace
------------------------

A workspace is a set of pipelines that can run in certain order

The workspace is defined by a yaml that can look similar to the following
```yaml
name: coolspace
scm: git@github.com
organizations:
  - coolorg
workspace:
  - 3rdparties:
    - curlpp
    - nlohmann-json
    - stduuid
    - aws-sdk-cpp
  - core:
    - graphics
    - logger
```

Where you can define which organizations in the scm to look for the repo

And define the workspace layout, and who depends on who

Along with that, you may also define settings that can propogate to the pipelines in a workspace level

Those settings can be divided by system

The workspace can be initialized by running the following command

```shell
octo workspace init --org=pas --name=coolorg-ws
```

This will try to find the workspace and clone it, and along with it, clone the entire actual workspace definition

If you do not wish to also sync the workspace on init, add --no-sync

And you can later run the sync yourself with
```shell
octo workspace sync
```

Afterwards, you may choose to run any of the following commands

```shell
octo workspace execute all
octo workspace execute-action all build
octo workspace execute 3rdparties
octo workspace execute graphics
octo workspace execute-action graphics build
octo workspace clean all
octo workspace clean-action all build
octo workspace clean 3rdparties
octo workspace clean graphics
octo workspace clean-action graphics build
octo workspace describe
```

The above commands can execute the entire workspace pipeline, specific pipeline based on the workspace yml, or cleanup accordingly
