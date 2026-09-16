"""Optional contract test against a sibling checkout of Django-auth-service."""

import json
import os
import subprocess
from pathlib import Path

import jwt
import pytest
from rest_framework.test import APIClient

from tasks.authentication import jwks_client

pytestmark = pytest.mark.django_db


def test_real_auth_login_refresh_and_jwks(monkeypatch, settings):
    checkout = os.environ.get("AUTH_SERVICE_DIR")
    if not checkout:
        pytest.skip("Set AUTH_SERVICE_DIR to run the cross-service contract test")
    root = Path(checkout).resolve()
    script = """
import json
import django
from django.conf import settings
settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
django.setup()
from django.core.management import call_command
from rest_framework.test import APIClient
call_command("migrate", verbosity=0)
client = APIClient()
registered = client.post("/users/register/", {"username": "contract-user", "password": "Contract-Pass-92!"})
assert registered.status_code == 201, registered.data
login = client.post("/auth/login/", {"username": "contract-user", "password": "Contract-Pass-92!"})
assert login.status_code == 200, login.data
refreshed = client.post("/auth/refresh/", {"refresh": login.data["refresh"]})
assert refreshed.status_code == 200, refreshed.data
keys = client.get("/auth/jwks.json")
assert keys.status_code == 200
print(json.dumps({"tokens": login.data, "refreshed": refreshed.data, "jwks": keys.data}))
"""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "ENVIRONMENT": "local",
        "ALLOWED_HOSTS": "testserver",
        "LOGGING_ENABLED": "false",
        "SILK_ENABLED": "false",
        "ZEAL_ENABLED": "false",
        "JWT_AUDIENCE": "tasks-service",
    }
    result = subprocess.run(
        [str(root / ".venv/bin/python"), "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    contract = json.loads(result.stdout)
    settings.AUTH_JWT_AUDIENCE = "tasks-service"
    settings.AUTH_JWKS_URL = "http://contract.test/auth/jwks.json"
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: contract["jwks"])
    jwks_client.cache_clear()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {contract['tokens']['access']}")
    created = client.post("/api/tasks/", {"title": "Real auth token"})
    assert created.status_code == 201
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {contract['refreshed']['access']}")
    assert client.get("/api/tasks/").data["count"] == 1
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {contract['refreshed']['refresh']}")
    assert client.get("/api/tasks/").status_code == 401
    jwks_client.cache_clear()
