import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings
from jwt.algorithms import RSAAlgorithm
from rest_framework.test import APIClient

from apps.tasks.authentication import jwks_client

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def keys():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def issuer(keys, settings):
    jwk = RSAAlgorithm.to_jwk(keys.public_key(), as_dict=True)
    jwk.update(kid="test-key", alg="RS256", use="sig")
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            body = json.dumps({"keys": [jwk]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings.AUTH_JWKS_URL = f"http://127.0.0.1:{server.server_port}/.well-known/jwks.json"
    settings.AUTH_JWT_AUDIENCE = None
    jwks_client.cache_clear()
    yield hits
    server.shutdown()
    server.server_close()
    thread.join()
    jwks_client.cache_clear()


@pytest.fixture
def token(keys, issuer):
    def issue(**overrides):
        claims = {
            "user_id": str(uuid4()),
            "token_type": "access",
            "jti": str(uuid4()),
            "iss": "django-template-auth",
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
        }
        claims.update(overrides)
        return jwt.encode(claims, keys, algorithm="RS256", headers={"kid": "test-key"})

    return issue


def client_for(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def test_owner_crud_and_jwks_cache(token, issuer):
    owner = str(uuid4())
    client = client_for(token(user_id=owner))
    created = client.post("/api/v1/tasks/", {"title": "First task", "owner_id": str(uuid4())})
    assert created.status_code == 201
    assert created.data["owner_id"] == owner
    url = f"/api/v1/tasks/{created.data['id']}/"
    assert client.get("/api/v1/tasks/").data["count"] == 1
    assert client.get(url).status_code == 200
    assert client.patch(url, {"completed": True}).data["completed"] is True
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert len(issuer) == 1


def test_other_user_cannot_read_update_delete(token):
    alice = client_for(token())
    created = alice.post("/api/v1/tasks/", {"title": "Private"})
    url = f"/api/v1/tasks/{created.data['id']}/"
    bob = client_for(token())
    assert bob.get("/api/v1/tasks/").data["count"] == 0
    assert bob.get(url).status_code == 404
    assert bob.patch(url, {"title": "Stolen"}).status_code == 404
    assert bob.delete(url).status_code == 404
    assert alice.get(url).data["title"] == "Private"


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"iss": "other"},
        {"token_type": "refresh"},
        {"user_id": "bad-id"},
        {"iat": int(time.time()) + 3600},
        {"exp": None},
    ],
)
def test_invalid_claims(token, claims):
    response = client_for(token(**claims)).get("/api/v1/tasks/")
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"


def test_no_token():
    assert APIClient().get("/api/v1/tasks/").status_code == 401


def test_wrong_signature(token):
    raw = token()
    claims = jwt.decode(raw, options={"verify_signature": False})
    forged = jwt.encode(
        claims,
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    assert client_for(forged).get("/api/v1/tasks/").status_code == 401


@pytest.mark.parametrize("kid", ["unknown", ""])
def test_wrong_key_id(keys, token, kid):
    claims = jwt.decode(token(), options={"verify_signature": False})
    raw = jwt.encode(claims, keys, algorithm="RS256", headers={"kid": kid})
    assert client_for(raw).get("/api/v1/tasks/").status_code == 401


def test_audience(token):
    with override_settings(AUTH_JWT_AUDIENCE="tasks-service"):
        assert client_for(token(aud="tasks-service")).get("/api/v1/tasks/").status_code == 200
        assert client_for(token(aud="other")).get("/api/v1/tasks/").status_code == 401
        assert client_for(token()).get("/api/v1/tasks/").status_code == 401


def test_unavailable_jwks(token, monkeypatch):
    def fail(*args, **kwargs):
        raise jwt.PyJWKClientConnectionError("unavailable")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fail)
    assert client_for(token()).get("/api/v1/tasks/").status_code == 503


def test_wrong_algorithm(issuer):
    raw = jwt.encode(
        {"user_id": str(uuid4())},
        "test-secret-at-least-thirty-two-bytes",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )
    assert client_for(raw).get("/api/v1/tasks/").status_code == 401
    assert issuer == []
