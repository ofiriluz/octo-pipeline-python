"""Unit tests for the macOS-support changes: build_policy and the clang / apple-clang version widening.

All collaborators are stubbed, so no Artifactory, conan home or compiler is needed.
"""
from unittest import mock

import pytest

from octo_pipeline_python.backends.conan.actions.conan_consume import \
    ConanConsume
from octo_pipeline_python.backends.conan.conan_backend import ConanBackend
from octo_pipeline_python.backends.conan.models import ConanModel


def make_pipeline():
    pipeline = mock.MagicMock()
    pipeline.name = "test-pipeline"  # MagicMock(name=...) would set the mock's repr, not the attribute
    pipeline.source_dir = "/tmp/src"
    return pipeline


# --------------------------------------------------------------------------- build_policy

def test_build_policy_defaults_to_never_build():
    assert ConanModel().build_policy is None


def run_consume(build_policy):
    conan_client = mock.MagicMock()
    conan_client.install.return_value = {"error": True, "installed": []}  # skips result parsing
    backend = mock.MagicMock()
    backend.backend_name.return_value = "conan"
    backend.backend_args.return_value = ConanModel(build_policy=build_policy)
    ctx = mock.MagicMock()
    ctx.attribute.side_effect = lambda _backend, name, tag=None: {
        "conan_client": conan_client,
        "conan_dir.configurations": ["debug"],
        "profile": "p",
    }.get(name, "/tmp/x")
    ConanConsume().execute(backend, ctx, make_pipeline(), mock.MagicMock(), None)
    return conan_client.install.call_args.kwargs["build"]


def test_consume_passes_build_policy_to_conan_install():
    assert run_consume("missing") == ["missing"]


def test_consume_without_build_policy_keeps_never_build():
    assert run_consume(None) is None


# --------------------------------------------------------------------------- clang / apple-clang widening

# Mirrors conan 1.66: multi-line apple-clang and clang lists, and an intel section that also lists "17".
SETTINGS_YML = """\
os: [Windows, Linux, Macos]
compiler:
    apple-clang: &apple_clang
        version: ["5.0", "5.1", "6.0",
                  "13", "13.0", "14", "14.0", "15", "15.0", "16", "16.0"]
        libcxx: [libstdc++, libc++]
    clang:
        version: ["3.3", "3.4",
                  "15", "16", "17"]
        libcxx: [None, libstdc++, libc++]
    intel:
        version: ["11", "12", "17", "18"]
"""


def configure_profile(conan_dir, detected_version, compiler="apple-clang"):
    conan_client = mock.MagicMock()
    conan_client.profile_list.return_value = ["test-pipeline"]  # profile exists, skip creation
    conan_client.get_profile_key.side_effect = lambda _profile, key: {
        "settings.compiler": compiler,
        "settings.compiler.version": detected_version,
    }[key]
    ctx = mock.MagicMock()
    ctx.attribute.side_effect = lambda _backend, name, tag=None: {
        "conan_client": conan_client,
        "conan_dir": str(conan_dir),
    }[name]
    ConanBackend._ConanBackend__configure_profile(ConanModel(), ctx, make_pipeline())


@pytest.fixture
def settings_yml(tmp_path):
    path = tmp_path / ".conan" / "settings.yml"
    path.parent.mkdir()
    path.write_text(SETTINGS_YML)
    return path


def test_widening_adds_missing_version_to_apple_clang_only(tmp_path, settings_yml):
    configure_profile(tmp_path, "17")
    content = settings_yml.read_text()
    assert '"16", "16.0", "17"]' in content
    # Regression: the intel section already contained "17" and used to fool the check
    assert 'version: ["11", "12", "17", "18"]' in content
    # The clang list (which already has "17") must not be touched
    assert '"15", "16", "17"]' in content
    assert content.count('"17"') == 3


def test_widening_is_idempotent(tmp_path, settings_yml):
    configure_profile(tmp_path, "17")
    after_first = settings_yml.read_text()
    configure_profile(tmp_path, "17")
    assert settings_yml.read_text() == after_first


def test_widening_leaves_file_alone_when_version_already_listed(tmp_path, settings_yml):
    configure_profile(tmp_path, "16")
    assert settings_yml.read_text() == SETTINGS_YML


def test_widening_adds_missing_version_to_clang_only(tmp_path, settings_yml):
    configure_profile(tmp_path, "19", compiler="clang")
    content = settings_yml.read_text()
    assert '"15", "16", "17", "19"]' in content
    # apple-clang must not be touched by the 'clang' match
    assert '"15", "15.0", "16", "16.0"]' in content
    assert 'version: ["11", "12", "17", "18"]' in content


def test_widening_ignores_other_compilers(tmp_path, settings_yml):
    configure_profile(tmp_path, "13", compiler="gcc")
    assert settings_yml.read_text() == SETTINGS_YML


def test_widening_tolerates_a_missing_settings_file(tmp_path):
    configure_profile(tmp_path, "17")  # no .conan/settings.yml: must not raise
