"""Unit tests for Windows packaging helpers (filesystem only — no AWS/CodeBuild)."""

import zipfile
from pathlib import Path

from ccwb_wizard.api import package as pkg


def test_render_install_bat_bakes_profile_and_region():
    bat = pkg._render_install_bat("corp-prod", "ap-northeast-2")
    assert "set \"PROFILE_NAME=corp-prod\"" in bat
    assert "set \"REGION=ap-northeast-2\"" in bat
    assert "__PROFILE__" not in bat and "__REGION__" not in bat


def test_render_install_bat_defaults_region():
    bat = pkg._render_install_bat("p", "")
    assert "set \"REGION=us-east-1\"" in bat


def test_build_windows_source_zip_layout(tmp_path: Path):
    out = tmp_path / "source.zip"
    pkg.build_windows_source_zip(out)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    # Buildspec compiles source/credential_provider/__main__.py
    assert any(n == "source/credential_provider/__main__.py" for n in names)
    assert any(n.endswith("source/credential_provider/bedrock_metadata.py") for n in names)
    assert not any("__pycache__" in n for n in names)


def test_merge_windows_binary_extracts_exe(tmp_path: Path):
    artifact = tmp_path / "windows-binaries.zip"
    with zipfile.ZipFile(artifact, "w") as zf:
        zf.writestr("credential-process-windows.exe", b"MZ\x00fake-exe")
    dist = tmp_path / "dist"
    dist.mkdir()
    out = pkg.merge_windows_binary(artifact, dist)
    assert out.exists()
    assert out.name == "credential-process-windows.exe"
    assert out.read_bytes().startswith(b"MZ")


def test_merge_windows_binary_missing_raises(tmp_path: Path):
    artifact = tmp_path / "empty.zip"
    with zipfile.ZipFile(artifact, "w") as zf:
        zf.writestr("notes.txt", b"nothing")
    dist = tmp_path / "dist"
    dist.mkdir()
    try:
        pkg.merge_windows_binary(artifact, dist)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "credential-process-windows.exe" in str(e)
