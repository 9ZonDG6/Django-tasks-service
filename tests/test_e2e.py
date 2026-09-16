"""Two independent Django processes, databases and real HTTP requests."""

import base64
import json
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def request(url, data=None, token=None, method=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read()
        return response.status, json.loads(body) if body else None


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def server(root, port, database, env, log):
    script = """
import sys
from django.conf import settings
settings.DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": sys.argv[1]}
import django
django.setup()
from django.core.management import call_command
call_command("migrate", verbosity=0)
call_command("runserver", sys.argv[2], use_reloader=False, verbosity=0)
"""
    with log.open("w+") as output:
        process = subprocess.Popen(
            [str(root / ".venv/bin/python"), "-c", script, str(database), f"127.0.0.1:{port}"],
            cwd=root,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(200):
                if process.poll() is not None:
                    output.seek(0)
                    pytest.fail(output.read())
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                pytest.fail("Service did not start within 20 seconds")
            yield f"http://127.0.0.1:{port}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def test_auth_and_tasks_over_http(tmp_path):
    checkout = os.environ.get("AUTH_SERVICE_DIR")
    if not checkout:
        pytest.skip("Set AUTH_SERVICE_DIR to run two-service HTTP E2E")
    auth_root = Path(checkout).resolve()
    tasks_root = Path(__file__).resolve().parents[1]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    auth_port, tasks_port = unused_port(), unused_port()
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "ENVIRONMENT": "local",
        "DEBUG": "true",
        "SECRET_KEY": "isolated-e2e-test-only",
        "ALLOWED_HOSTS": "127.0.0.1,localhost",
        "SILK_ENABLED": "false",
        "ZEAL_ENABLED": "false",
        "LOGGING_ENABLED": "false",
        "JWT_SIGNING_KEY": base64.b64encode(private).decode(),
        "JWT_VERIFYING_KEY": base64.b64encode(public).decode(),
        "JWT_ISSUER": "e2e-auth",
        "JWT_AUDIENCE": "tasks-service",
        "AUTH_JWT_ISSUER": "e2e-auth",
        "AUTH_JWT_AUDIENCE": "tasks-service",
        "AUTH_JWKS_URL": f"http://127.0.0.1:{auth_port}/.well-known/jwks.json",
    }
    with (
        server(auth_root, auth_port, tmp_path / "auth.sqlite3", env, tmp_path / "auth.log") as auth,
        server(tasks_root, tasks_port, tmp_path / "tasks.sqlite3", env, tmp_path / "tasks.log") as tasks,
    ):
        tokens = []
        for username in ("alice", "bob"):
            credentials = {"username": username, "password": "E2E-Strong-Password-92!"}
            assert request(auth + "/api/v1/users/register/", credentials)[0] == 201
            code, pair = request(auth + "/api/v1/auth/login/", credentials)
            assert code == 200
            tokens.append(pair)
        alice, bob = tokens
        assert request(auth + "/.well-known/jwks.json")[0] == 200
        assert request(tasks + "/api/v1/tasks/")[0] == 401
        code, task = request(tasks + "/api/v1/tasks/", {"title": "HTTP integration"}, alice["access"])
        assert code == 201
        detail = tasks + f"/api/v1/tasks/{task['id']}/"
        assert request(detail, token=alice["access"])[0] == 200
        assert request(detail, token=bob["access"])[0] == 404
        assert request(detail, {"title": "stolen"}, bob["access"], "PATCH")[0] == 404
        assert request(detail, token=bob["access"], method="DELETE")[0] == 404
        assert request(tasks + "/api/v1/tasks/", token=alice["refresh"])[0] == 401
        code, refreshed = request(auth + "/api/v1/auth/refresh/", {"refresh": alice["refresh"]})
        assert code == 200
        assert request(detail, token=refreshed["access"])[0] == 200
        assert request(auth + "/api/v1/auth/refresh/", {"refresh": alice["refresh"]})[0] == 401
        assert request(auth + "/api/v1/auth/logout/", {"refresh": refreshed["refresh"]}, refreshed["access"])[0] == 205
        assert request(auth + "/api/v1/auth/refresh/", {"refresh": refreshed["refresh"]})[0] == 401
        assert request(detail, token=refreshed["access"], method="DELETE")[0] == 204
