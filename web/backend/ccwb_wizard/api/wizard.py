"""Profile + Draft CRUD API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ccwb_domain.config import Config, UnsupportedSchemaError
from ..settings import PROFILES_DIR

router = APIRouter(tags=["wizard"])


class ProfileResponse(BaseModel):
    profile_name: str
    data: dict


# --- Profile CRUD ---

@router.get("/profile")
async def list_profiles() -> list[str]:
    """List all profile names."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return [p.stem for p in PROFILES_DIR.glob("*.json") if not p.stem.endswith(".draft")]


@router.get("/profile/{name}")
async def get_profile(name: str) -> dict:
    """Load a profile by name."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    try:
        config = Config.load(path)
        return config.to_dict()
    except UnsupportedSchemaError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/profile/{name}")
async def save_profile(name: str, body: dict) -> dict:
    """Create or update a profile."""
    body["profile_name"] = name
    config = Config(**{k: v for k, v in body.items() if k in Config.__dataclass_fields__})
    path = PROFILES_DIR / f"{name}.json"
    config.save(path)
    return {"status": "saved", "profile_name": name}


@router.delete("/profile/{name}")
async def delete_profile(name: str) -> dict:
    """Delete a profile."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    path.unlink()
    # Also delete draft if exists
    draft_path = PROFILES_DIR / f"{name}.draft.json"
    if draft_path.exists():
        draft_path.unlink()
    return {"status": "deleted", "profile_name": name}


# --- Draft CRUD ---

@router.get("/profile/{name}/draft")
async def get_draft(name: str) -> dict:
    """Load a draft for a profile."""
    path = PROFILES_DIR / f"{name}.draft.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Draft for '{name}' not found")
    try:
        config = Config.load(path)
        return config.to_dict()
    except UnsupportedSchemaError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/profile/{name}/draft")
async def save_draft(name: str, body: dict) -> dict:
    """Save a draft (auto-saved on page transitions)."""
    body["profile_name"] = name
    config = Config(**{k: v for k, v in body.items() if k in Config.__dataclass_fields__})
    path = PROFILES_DIR / f"{name}.draft.json"
    config.save(path)
    return {"status": "draft_saved", "profile_name": name}


# --- Materialize preview ---

@router.post("/profile/{name}/materialize")
async def materialize_preview(name: str) -> dict:
    """Generate DeploymentArtifacts preview from saved profile."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")

    from ccwb_domain.config import Config as DomainConfig
    from ccwb_domain.materialize import materialize

    config = DomainConfig.load(path)
    artifacts = materialize(config)
    return artifacts.to_review_dict()
