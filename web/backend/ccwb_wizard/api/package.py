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

    return {"profiles": {config.profile_name: profile_config}}


INSTALL_SH_TEMPLATE = r'''#!/bin/bash
set -e
echo "=== Claude Code with Bedrock — Installer ==="
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

    # 4. Write install.sh
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
