"""Package API — build credential-process binary + installer zip.

POST /api/profile/{name}/package
  → Builds credential-process for current platform using PyInstaller.
  → Assembles dist/ with config.json, install.sh, settings.json template.
  → Returns package info (path, size, platform).

GET /api/profile/{name}/package/status
  → Returns existing package info if available.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import boto3

from ccwb_domain.config import Config
from ccwb_domain.materialize import materialize
from ..settings import PROFILES_DIR

router = APIRouter(tags=["package"])

# Paths
CREDENTIAL_PROVIDER_DIR = Path(__file__).resolve().parents[4] / "web" / "binaries" / "credential_provider"
DIST_BASE = Path(__file__).resolve().parents[4] / "dist"


def _detect_platform() -> str:
    """Detect current platform for binary naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return f"macos-{'arm64' if machine == 'arm64' else 'intel'}"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    return f"{system}-{machine}"


def _build_binary(dist_dir: Path, platform_name: str) -> Path:
    """Build credential-process binary using PyInstaller."""
    binary_name = f"credential-process-{platform_name}"
    if platform_name == "windows":
        binary_name += ".exe"

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", binary_name,
        "--distpath", str(dist_dir),
        "--workpath", str(dist_dir / "_build"),
        "--specpath", str(dist_dir / "_build"),
        "--clean",
        "--collect-all", "keyring",
        "--collect-all", "jwt",
        "--collect-all", "cryptography",
        "--hidden-import", "credential_provider.bedrock_metadata",
        str(CREDENTIAL_PROVIDER_DIR / "__main__.py"),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller failed:\n{result.stderr[-2000:]}")

    binary_path = dist_dir / binary_name
    if not binary_path.exists():
        raise RuntimeError(f"Binary not found after build: {binary_path}")
    return binary_path


def _generate_config_json(config: Config) -> dict:
    """Generate credential-process config.json from Config 3.0 profile.

    This is the bridge between wizard-managed profiles and the credential-process
    runtime. The config.json in the package allows credential-process to work
    without needing ~/.ccwb/profiles/ (for distributed packages).
    """
    provider = config.provider
    ptype = provider.get("type", "generic")

    profile_config: dict[str, Any] = {
        "provider_type": ptype,
        "client_id": provider.get("client_id", ""),
        "aws_region": config.aws_region,
        "credential_storage": "keyring",
        "federation_type": "direct",
        "federated_role_arn": provider.get("federated_role_arn", ""),
    }

    # Provider-specific domain
    if ptype == "okta":
        profile_config["provider_domain"] = provider.get("domain", "")
    elif ptype == "auth0":
        profile_config["provider_domain"] = provider.get("domain", "")
    elif ptype == "azure":
        tenant = provider.get("tenant_id", "")
        profile_config["provider_domain"] = f"https://login.microsoftonline.com/{tenant}"
        profile_config["azure_auth_mode"] = provider.get("auth_mode", "public")
    elif ptype == "cognito":
        domain = provider.get("user_pool_domain", "")
        # credential-process prepends https:// itself, so store bare host
        if domain and "." not in domain:
            profile_config["provider_domain"] = f"{domain}.auth.{config.aws_region}.amazoncognito.com"
        else:
            # Strip scheme if present (credential-process adds it)
            profile_config["provider_domain"] = domain.replace("https://", "").replace("http://", "")
    elif ptype == "generic":
        profile_config["provider_domain"] = provider.get("issuer_url", "")
        profile_config["oidc_authorization_endpoint"] = provider.get("authorization_endpoint", "")
        profile_config["oidc_token_endpoint"] = provider.get("token_endpoint", "")

    # Attribution mapping (dynamic binding)
    if config.attribution:
        profile_config["attribution"] = config.attribution

    # Quota enforcement (credential-process calls the quota check API before issuing creds).
    # Only wired when the quota stack has been deployed and its endpoint synced into the
    # profile (config.quota.api_endpoint). Without quota_api_endpoint the provider skips
    # quota checks entirely (_should_check_quota → False).
    if config.quota and config.quota.get("api_endpoint"):
        profile_config["quota_api_endpoint"] = config.quota["api_endpoint"]
        profile_config["quota_check_interval"] = config.quota.get("check_interval", 30)
        profile_config["quota_fail_mode"] = config.quota.get("fail_mode", "open")
        profile_config["quota_check_timeout"] = config.quota.get("check_timeout", 5)

    return {"profiles": {config.profile_name: profile_config}}


INSTALL_SH_TEMPLATE = r'''#!/bin/bash
set -e
echo "=== Claude Code with Bedrock — Installer ==="
echo ""

# --- Dependency checks (advisory; we do not auto-install) ---
# Claude Code itself is assumed to be installed by the user beforehand.
if ! command -v aws >/dev/null 2>&1; then
  echo "WARNING: AWS CLI not found on PATH."
  echo "  Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "WARNING: 'claude' (Claude Code) not found on PATH. Install it before first use:"
  echo "  https://code.claude.com/docs"
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "WARNING: python3 not found — falling back to default profile name/region."
fi
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/claude-code-with-bedrock"

mkdir -p "$INSTALL_DIR"

# Copy binary
PLATFORM=$(uname -m)
case "$PLATFORM" in
  arm64) BIN="credential-process-macos-arm64" ;;
  x86_64)
    if [[ "$(uname -s)" == "Darwin" ]]; then BIN="credential-process-macos-intel"
    else BIN="credential-process-linux"; fi ;;
  *) BIN="credential-process-linux" ;;
esac

if [[ ! -f "$SCRIPT_DIR/$BIN" ]]; then
  echo "ERROR: Binary $BIN not found in package."
  exit 1
fi

cp "$SCRIPT_DIR/$BIN" "$INSTALL_DIR/credential-process"
chmod +x "$INSTALL_DIR/credential-process"

# Copy config
cp "$SCRIPT_DIR/config.json" "$INSTALL_DIR/config.json"

# Setup ~/.aws/config
AWS_CONFIG="$HOME/.aws/config"
mkdir -p "$HOME/.aws"
PROFILE_NAME=$(python3 -c "import json;d=json.load(open('$INSTALL_DIR/config.json'));print(list(d.get('profiles',d).keys())[0])" 2>/dev/null || echo "ClaudeCode")

if grep -q "\[profile $PROFILE_NAME\]" "$AWS_CONFIG" 2>/dev/null; then
  echo "AWS profile [$PROFILE_NAME] already exists in $AWS_CONFIG — skipping."
else
  cat >> "$AWS_CONFIG" << EOF

[profile $PROFILE_NAME]
region = $(python3 -c "import json;d=json.load(open('$INSTALL_DIR/config.json'));p=list(d.get('profiles',d).values())[0];print(p.get('aws_region','us-east-1'))" 2>/dev/null || echo "us-east-1")
credential_process = "$INSTALL_DIR/credential-process" --profile $PROFILE_NAME
EOF
  echo "Added [$PROFILE_NAME] to $AWS_CONFIG"
fi

# Setup Claude settings.json
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
if [[ -f "$SCRIPT_DIR/settings.json" ]]; then
  mkdir -p "$HOME/.claude"
  cp "$SCRIPT_DIR/settings.json" "$CLAUDE_SETTINGS"
  echo "Installed Claude settings to $CLAUDE_SETTINGS"
fi

echo ""
echo "✓ Installation complete!"
echo "  Binary: $INSTALL_DIR/credential-process"
echo "  Config: $INSTALL_DIR/config.json"
echo ""
echo "Run first authentication:"
echo "  $INSTALL_DIR/credential-process --profile $PROFILE_NAME"
echo ""
echo "Then start Claude Code — it will use Bedrock automatically."
'''


# Windows installer. Profile name + region are baked in at package time (no JSON
# parsing in cmd.exe). Mirrors install.sh: place binary, write ~/.aws/config, settings.
INSTALL_BAT_TEMPLATE = r'''@echo off
setlocal
echo === Claude Code with Bedrock - Installer ===
echo.

where aws >nul 2>nul || echo WARNING: AWS CLI not found on PATH. See https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
where claude >nul 2>nul || echo WARNING: 'claude' (Claude Code) not found on PATH. Install it before first use: https://code.claude.com/docs
echo.

set "SCRIPT_DIR=%~dp0"
set "INSTALL_DIR=%USERPROFILE%\claude-code-with-bedrock"
set "PROFILE_NAME=__PROFILE__"
set "REGION=__REGION__"

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

if not exist "%SCRIPT_DIR%credential-process-windows.exe" (
  echo ERROR: credential-process-windows.exe not found in package.
  exit /b 1
)
copy /Y "%SCRIPT_DIR%credential-process-windows.exe" "%INSTALL_DIR%\credential-process.exe" >nul
copy /Y "%SCRIPT_DIR%config.json" "%INSTALL_DIR%\config.json" >nul

set "AWS_CONFIG=%USERPROFILE%\.aws\config"
if not exist "%USERPROFILE%\.aws" mkdir "%USERPROFILE%\.aws"
findstr /C:"[profile %PROFILE_NAME%]" "%AWS_CONFIG%" >nul 2>nul
if errorlevel 1 (
  >>"%AWS_CONFIG%" echo.
  >>"%AWS_CONFIG%" echo [profile %PROFILE_NAME%]
  >>"%AWS_CONFIG%" echo region = %REGION%
  >>"%AWS_CONFIG%" echo credential_process = "%INSTALL_DIR%\credential-process.exe" --profile %PROFILE_NAME%
  echo Added [%PROFILE_NAME%] to %AWS_CONFIG%
) else (
  echo AWS profile [%PROFILE_NAME%] already exists - skipping.
)

if exist "%SCRIPT_DIR%settings.json" (
  if not exist "%USERPROFILE%\.claude" mkdir "%USERPROFILE%\.claude"
  copy /Y "%SCRIPT_DIR%settings.json" "%USERPROFILE%\.claude\settings.json" >nul
  echo Installed Claude settings to %USERPROFILE%\.claude\settings.json
)

echo.
echo Installation complete.
echo   Run first authentication:
echo     "%INSTALL_DIR%\credential-process.exe" --profile %PROFILE_NAME%
endlocal
'''


def _render_install_bat(profile_name: str, region: str) -> str:
    """Bake the profile name + region into the Windows installer."""
    return INSTALL_BAT_TEMPLATE.replace("__PROFILE__", profile_name).replace("__REGION__", region or "us-east-1")


def build_windows_source_zip(dest_zip: Path) -> Path:
    """Assemble the CodeBuild source.zip with the layout the buildspec expects.

    Buildspec builds ``source/credential_provider/__main__.py`` (Nuitka), so the zip
    must contain the package under a top-level ``source/`` directory.
    """
    import zipfile

    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    src = CREDENTIAL_PROVIDER_DIR
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*"):
            if f.is_dir() or "__pycache__" in f.parts:
                continue
            arcname = Path("source") / "credential_provider" / f.relative_to(src)
            zf.write(f, str(arcname))
    return dest_zip


def merge_windows_binary(artifact_zip: Path, dist_dir: Path) -> Path:
    """Extract credential-process-windows.exe from a CodeBuild artifact zip into dist."""
    import zipfile

    with zipfile.ZipFile(artifact_zip) as zf:
        member = next((n for n in zf.namelist() if n.endswith("credential-process-windows.exe")), None)
        if not member:
            raise RuntimeError("credential-process-windows.exe not found in build artifact")
        data = zf.read(member)
    out = dist_dir / "credential-process-windows.exe"
    out.write_bytes(data)
    return out


def assemble_windows_package(config: Config, name: str, artifact_zip: Path) -> Path:
    """Build the self-contained Windows zip: .exe + config.json + settings.json + install.bat.

    Regenerates config/settings so the Windows package is independent of the
    macOS/Linux Package step. Returns the zip path (<profile>-windows.zip).
    """
    winpkg = DIST_BASE / name / "_winpkg"
    if winpkg.exists():
        shutil.rmtree(winpkg)
    winpkg.mkdir(parents=True)

    merge_windows_binary(artifact_zip, winpkg)  # credential-process-windows.exe
    (winpkg / "config.json").write_text(
        json.dumps(_generate_config_json(config), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (winpkg / "settings.json").write_text(
        json.dumps(materialize(config).settings_json_template, indent=2) + "\n", encoding="utf-8"
    )
    (winpkg / "install.bat").write_text(
        _render_install_bat(name, config.aws_region), encoding="utf-8"
    )

    zip_path = DIST_BASE / f"{name}-windows.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(winpkg))
    shutil.rmtree(winpkg)
    return zip_path


@router.post("/profile/{name}/package")
async def build_package(name: str) -> dict:
    """Build distribution package for a profile."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")

    config = Config.load(path)
    artifacts = materialize(config)

    # Prepare dist directory
    dist_dir = DIST_BASE / name
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    platform_name = _detect_platform()

    # 1. Build binary
    try:
        binary_path = _build_binary(dist_dir, platform_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Binary build failed: {e}")

    # 2. Write config.json (needs federated_role_arn from deployed auth stack)
    # Reload profile to get synced outputs (e.g. federated_role_arn from deploy)
    config = Config.load(path)
    config_json = _generate_config_json(config)
    (dist_dir / "config.json").write_text(
        json.dumps(config_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # 3. Write settings.json template
    (dist_dir / "settings.json").write_text(
        json.dumps(artifacts.settings_json_template, indent=2) + "\n", encoding="utf-8"
    )

    # 4. install.sh — this is the self-contained macOS/Linux package.
    #    Windows users get a separate self-contained <profile>-windows.zip (install.bat
    #    + credential-process-windows.exe) produced by the CodeBuild flow below.
    (dist_dir / "install.sh").write_text(INSTALL_SH_TEMPLATE, encoding="utf-8")
    (dist_dir / "install.sh").chmod(0o755)

    # 5. Create zip (exclude _build/ artifacts)
    zip_path = DIST_BASE / f"{name}-{platform_name}.zip"
    build_dir = dist_dir / "_build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(dist_dir))

    return {
        "status": "success",
        "profile_name": name,
        "platform": platform_name,
        "dist_dir": str(dist_dir),
        "zip_path": str(zip_path),
        "zip_size_mb": round(zip_path.stat().st_size / 1024 / 1024, 2),
        "contents": [f.name for f in dist_dir.iterdir() if not f.name.startswith("_")],
    }


@router.get("/profile/{name}/package/status")
async def package_status(name: str) -> dict:
    """Check if a package exists for a profile."""
    dist_dir = DIST_BASE / name
    if not dist_dir.exists():
        return {"status": "not_built", "profile_name": name}

    contents = [f.name for f in dist_dir.iterdir() if not f.name.startswith("_")]
    platform_name = _detect_platform()
    zip_path = DIST_BASE / f"{name}-{platform_name}.zip"

    return {
        "status": "available",
        "profile_name": name,
        "platform": platform_name,
        "dist_dir": str(dist_dir),
        "zip_path": str(zip_path) if zip_path.exists() else None,
        "zip_size_mb": round(zip_path.stat().st_size / 1024 / 1024, 2) if zip_path.exists() else None,
        "contents": contents,
    }


# ---------------------------------------------------------------------------
# Windows packaging via CodeBuild (cloud build — no Windows machine needed)
# ---------------------------------------------------------------------------
WINDOWS_ARTIFACT_KEY = "windows-binaries.zip"
WINDOWS_SOURCE_KEY = "source.zip"


def _codebuild_outputs(config: Config) -> dict:
    """Read BuildBucket + ProjectName from the deployed codebuild stack."""
    cfn = boto3.client("cloudformation", region_name=config.aws_region)
    stack_name = f"{config.stack_base_name}-codebuild"
    resp = cfn.describe_stacks(StackName=stack_name)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    if "BuildBucket" not in outputs or "ProjectName" not in outputs:
        raise HTTPException(status_code=409,
                            detail=f"{stack_name} missing BuildBucket/ProjectName outputs — deploy it first")
    return outputs


@router.post("/profile/{name}/package/windows")
async def start_windows_build(name: str) -> dict:
    """Upload source + trigger the Windows CodeBuild build. Poll via GET .../builds."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    config = Config.load(path)
    if not config.enable_codebuild_windows:
        raise HTTPException(status_code=400, detail="Windows builds not enabled for this profile")

    outputs = _codebuild_outputs(config)
    bucket, project = outputs["BuildBucket"], outputs["ProjectName"]

    dist_dir = DIST_BASE / name
    dist_dir.mkdir(parents=True, exist_ok=True)
    source_zip = dist_dir / "_windows-source.zip"
    build_windows_source_zip(source_zip)

    s3 = boto3.client("s3", region_name=config.aws_region)
    s3.upload_file(str(source_zip), bucket, WINDOWS_SOURCE_KEY)

    cb = boto3.client("codebuild", region_name=config.aws_region)
    build = cb.start_build(projectName=project)["build"]
    return {
        "status": "started",
        "profile_name": name,
        "build_id": build["id"],
        "project": project,
        "bucket": bucket,
    }


@router.get("/profile/{name}/builds")
async def windows_build_status(name: str) -> dict:
    """Poll the latest Windows build. On success, fetch the .exe into dist/."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    config = Config.load(path)
    outputs = _codebuild_outputs(config)
    bucket, project = outputs["BuildBucket"], outputs["ProjectName"]

    cb = boto3.client("codebuild", region_name=config.aws_region)
    ids = cb.list_builds_for_project(projectName=project).get("ids", [])
    if not ids:
        return {"status": "none", "profile_name": name, "message": "No builds yet"}
    build = cb.batch_get_builds(ids=ids[:1])["builds"][0]
    status = build.get("buildStatus", "UNKNOWN")
    result = {"status": status, "profile_name": name, "build_id": build["id"]}

    if status == "SUCCEEDED":
        dist_dir = DIST_BASE / name
        dist_dir.mkdir(parents=True, exist_ok=True)
        artifact_zip = dist_dir / "_windows-binaries.zip"
        s3 = boto3.client("s3", region_name=config.aws_region)
        try:
            s3.download_file(bucket, WINDOWS_ARTIFACT_KEY, str(artifact_zip))
            # Self-contained Windows package: .exe + config + settings + install.bat
            zip_path = assemble_windows_package(config, name, artifact_zip)
            artifact_zip.unlink(missing_ok=True)
            result["merged"] = True
            result["zip_path"] = str(zip_path)
            result["zip_size_mb"] = round(zip_path.stat().st_size / 1024 / 1024, 2)
        except Exception as e:
            result["merged"] = False
            result["message"] = f"Build succeeded but artifact assembly failed: {e}"
    return result
