"""Backend API integration tests using httpx + FastAPI TestClient."""

import pytest
from httpx import AsyncClient, ASGITransport

from ccwb_wizard.main import app


@pytest.fixture
def client():
    """Synchronous test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestScenarios:
    def test_get_scenarios(self, client):
        r = client.get("/api/scenarios")
        assert r.status_code == 200
        data = r.json()
        assert "providers" in data
        assert "distribution_types" in data
        assert "models" in data
        assert len(data["providers"]) == 5

    def test_get_providers(self, client):
        r = client.get("/api/scenarios/providers")
        assert r.status_code == 200
        providers = r.json()
        types = [p["type"] for p in providers]
        assert "okta" in types
        assert "azure" in types
        assert "cognito" in types
        assert "auth0" in types
        assert "generic" in types

    def test_get_models(self, client):
        r = client.get("/api/scenarios/models")
        assert r.status_code == 200
        models = r.json()
        assert "sonnet-4-6" in models
        assert "us" in models["sonnet-4-6"]["profiles"]


class TestProfileCRUD:
    def test_create_and_get_profile(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccwb_wizard.api.wizard.PROFILES_DIR", tmp_path)

        body = {
            "schema_version": "3.0",
            "aws_region": "us-east-1",
            "stack_base_name": "test",
            "provider": {"type": "okta", "domain": "t.okta.com", "client_id": "abc"},
            "model_id": "us.anthropic.claude-sonnet-4-6",
            "cross_region_profile": "us",
            "source_region": "us-east-1",
        }
        r = client.post("/api/profile/myprof", json=body)
        assert r.status_code == 200
        assert r.json()["status"] == "saved"

        r2 = client.get("/api/profile/myprof")
        assert r2.status_code == 200
        assert r2.json()["profile_name"] == "myprof"
        assert r2.json()["provider"]["type"] == "okta"

    def test_list_profiles(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccwb_wizard.api.wizard.PROFILES_DIR", tmp_path)
        # Create one
        client.post("/api/profile/x", json={"schema_version": "3.0", "provider": {}})
        r = client.get("/api/profile")
        assert r.status_code == 200
        assert "x" in r.json()

    def test_delete_profile(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccwb_wizard.api.wizard.PROFILES_DIR", tmp_path)
        client.post("/api/profile/del-me", json={"schema_version": "3.0", "provider": {}})
        r = client.delete("/api/profile/del-me")
        assert r.status_code == 200
        r2 = client.get("/api/profile/del-me")
        assert r2.status_code == 404

    def test_get_nonexistent_profile(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccwb_wizard.api.wizard.PROFILES_DIR", tmp_path)
        r = client.get("/api/profile/nope")
        assert r.status_code == 404


class TestDraft:
    def test_save_and_load_draft(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccwb_wizard.api.wizard.PROFILES_DIR", tmp_path)
        body = {"schema_version": "3.0", "provider": {"type": "auth0", "domain": "x.auth0.com", "client_id": "id"}}
        r = client.post("/api/profile/d/draft", json=body)
        assert r.status_code == 200
        assert r.json()["status"] == "draft_saved"

        r2 = client.get("/api/profile/d/draft")
        assert r2.status_code == 200
        assert r2.json()["provider"]["type"] == "auth0"


class TestMaterialize:
    def test_materialize_preview(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("ccwb_wizard.api.wizard.PROFILES_DIR", tmp_path)
        body = {
            "schema_version": "3.0",
            "stack_base_name": "mat-test",
            "provider": {"type": "okta", "domain": "x.okta.com", "client_id": "abc"},
            "model_id": "us.anthropic.claude-sonnet-4-6",
            "cross_region_profile": "us",
            "source_region": "us-east-1",
        }
        client.post("/api/profile/mat", json=body)
        r = client.post("/api/profile/mat/materialize")
        assert r.status_code == 200
        data = r.json()
        assert "stacks" in data
        stack_names = [s["stack_name"] for s in data["stacks"]]
        assert "mat-test-auth" in stack_names


class TestAWSLookup:
    def test_regions_list(self, client):
        r = client.get("/api/aws/regions")
        assert r.status_code == 200
        regions = r.json()
        assert "us-east-1" in regions
        assert len(regions) >= 20
