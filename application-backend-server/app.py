"""MyMiniCloud lab API: JSON students, MariaDB students and OIDC validation."""
from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
import threading
import time

from flask import Flask, jsonify, make_response, render_template, request
from jose import JWTError, jwt
import pymysql
import requests


ISSUER = os.getenv(
    "OIDC_ISSUER",
    "http://authentication-identity-server:8080/realms/realm_nhom13",
)
REALM = os.getenv("OIDC_REALM", "realm_nhom13")
# Keycloak sinh "iss" theo URL mà client dùng để lấy token, nên cùng một realm có thể
# xuất hiện dưới nhiều hostname (nội bộ Docker, localhost qua gateway, hay Public IP của EC2).
# Chữ ký token đã được xác minh bằng JWKS lấy từ issuer nội bộ (đáng tin cậy), nên phần
# "iss" chỉ cần khớp realm và thuộc danh sách host được phép.
ISSUER_ALIASES = tuple(
    item.strip()
    for item in os.getenv(
        "OIDC_ISSUER_ALIASES",
        "http://authentication-identity-server:8081/realms/realm_nhom13,"
        "http://localhost:8081/realms/realm_nhom13,"
        "http://localhost/realms/realm_nhom13",
    ).split(",")
    if item.strip()
)
# Host được phép xuất hiện trong "iss" (hỗ trợ ký tự đại diện, ví dụ "*.example.com").
ISSUER_HOST_ALLOWLIST = tuple(
    item.strip().lower()
    for item in os.getenv(
        "OIDC_ISSUER_HOST_ALLOWLIST",
        "authentication-identity-server,localhost,127.0.0.1,keycloak",
    ).split(",")
    if item.strip()
)
AUDIENCE = os.getenv("OIDC_AUDIENCE", "flask-app")
JWKS_URL = f"{ISSUER.rstrip('/')}/protocol/openid-connect/certs"
STUDENTS_FILE = Path(__file__).resolve().with_name("students.json")
JWKS_CACHE_SECONDS = 600
DEPENDENCY_TIMEOUT_SECONDS = 5

app = Flask(__name__)
app.json.ensure_ascii = False


class IdentityUnavailable(Exception):
    """The configured identity provider cannot supply usable signing keys."""


class SigningKeys:
    """Lazy, bounded-lifetime JWKS cache shared by requests in this process."""

    def __init__(self):
        self.keys = []
        self.expires_at = 0.0
        self.lock = threading.Lock()

    def load(self, *, force=False):
        with self.lock:
            if not force and self.keys and time.monotonic() < self.expires_at:
                return self.keys
            try:
                response = requests.get(JWKS_URL, timeout=DEPENDENCY_TIMEOUT_SECONDS)
                response.raise_for_status()
                document = response.json()
                keys = document.get("keys") if isinstance(document, dict) else None
                if not isinstance(keys, list) or not keys or not all(
                    isinstance(key, dict) for key in keys
                ):
                    raise ValueError("Invalid JWKS document")
            except (requests.RequestException, ValueError) as exc:
                raise IdentityUnavailable from exc
            self.keys = keys
            self.expires_at = time.monotonic() + JWKS_CACHE_SECONDS
            return self.keys

    def for_token(self, token):
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not kid:
            raise JWTError("Unsupported signing header")
        for force in (False, True):
            # A new kid may mean Keycloak rotated its signing key. Refresh once.
            for key in self.load(force=force):
                if (
                    key.get("kid") == kid
                    and key.get("kty") == "RSA"
                    and key.get("use", "sig") == "sig"
                    and key.get("alg", "RS256") == "RS256"
                ):
                    return key
        raise JWTError("Unknown signing key")


signing_keys = SigningKeys()


@app.get("/hello")
def hello():
    return jsonify(message="Hello from App Server!")


@app.get("/student")
def student():
    try:
        with STUDENTS_FILE.open(encoding="utf-8") as source:
            students = json.load(source)
        fields = {"id", "name", "major", "gpa"}
        if not isinstance(students, list) or len(students) != 5 or not all(
            isinstance(row, dict)
            and set(row) == fields
            and type(row["id"]) is int
            and isinstance(row["name"], str)
            and isinstance(row["major"], str)
            and type(row["gpa"]) in (int, float)
            and 0 <= row["gpa"] <= 4
            for row in students
        ):
            raise ValueError("Invalid student data")
        if len({row["id"] for row in students}) != 5:
            raise ValueError("Duplicate student ids")
    except (OSError, UnicodeError, ValueError):
        app.logger.error("Student JSON data is unavailable or invalid")
        return student_response(error="Student data unavailable", status=500)
    return student_response(students)


@app.get("/students-db")
def students_db():
    try:
        with pymysql.connect(
            host=os.getenv("DB_HOST", "relational-database-server"),
            port=3306,
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
            database=os.getenv("DB_NAME", "studentdb"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=DEPENDENCY_TIMEOUT_SECONDS,
            read_timeout=DEPENDENCY_TIMEOUT_SECONDS,
            write_timeout=DEPENDENCY_TIMEOUT_SECONDS,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, student_id, fullname, dob, major FROM students ORDER BY id"
                )
                students = cursor.fetchall()
        for row in students:
            if row["dob"] is not None:
                row["dob"] = row["dob"].isoformat()
        return student_response(students)
    except pymysql.MySQLError:
        app.logger.error("Student database is unavailable")
        return student_response(error="Database unavailable", status=503)


def student_response(students=None, *, error=None, status=200):
    """Render browser requests while preserving the API's default JSON contract."""
    payload = {"error": error} if error else students
    accept = request.accept_mimetypes
    wants_html = (
        request.args.get("format") != "json"
        and accept["text/html"] > accept["application/json"]
    )
    if wants_html:
        from_database = request.endpoint == "students_db"
        response = make_response(render_template(
            "students.html",
            students=students or [],
            from_database=from_database,
            error=error,
            status=status,
            raw_json=json.dumps(payload, ensure_ascii=False, indent=2),
        ), status)
    else:
        response = make_response(jsonify(payload), status)
    response.vary.add("Accept")
    return response


def unauthorized(message):
    response = jsonify(error=message)
    response.status_code = 401
    response.headers["WWW-Authenticate"] = "Bearer"
    return response


def issuer_accepted(issuer):
    """Chấp nhận "iss" của cùng realm khi host nằm trong danh sách cho phép.

    Chữ ký token đã được xác minh bằng JWKS lấy từ issuer nội bộ (nội bộ Docker
    là đường tin cậy), nên phần kiểm tra này chỉ chống việc dùng nhầm realm/token
    từ một nguồn khác chứ không phải cơ chế chống giả mạo chính.
    """
    if not isinstance(issuer, str) or not issuer:
        return False
    if issuer in (ISSUER,) + ISSUER_ALIASES:
        return True
    # Chấp nhận mọi cổng của host hợp lệ, ví dụ http://<public-ip>/realms/realm_nhom13.
    for prefix in ("http://", "https://"):
        if not issuer.startswith(prefix):
            continue
        remainder = issuer[len(prefix) :]
        host = remainder.split("/", 1)[0].split("@")[-1]
        hostname = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        hostname = hostname.lower()
        if not hostname:
            continue
        for allowed in ISSUER_HOST_ALLOWLIST:
            if hostname == allowed or fnmatch.fnmatch(hostname, allowed):
                return issuer.rstrip("/").endswith("/realms/" + REALM)
    return False


@app.get("/secure")
def secure():
    authorization = request.headers.get("Authorization", "").split()
    if len(authorization) != 2 or authorization[0].lower() != "bearer":
        return unauthorized("Missing or invalid Bearer token")
    token = authorization[1]
    try:
        key = signing_keys.for_token(token)
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUDIENCE,
            options={
                "require_exp": True,
                "require_iss": True,
                "require_aud": True,
                "verify_iss": False,
            },
        )
    except IdentityUnavailable:
        app.logger.error("Identity provider signing keys are unavailable")
        return jsonify(error="Identity provider unavailable"), 503
    except (JWTError, ValueError, TypeError, KeyError):
        return unauthorized("Invalid Bearer token")
    # Kiểm tra issuer thủ công để chấp nhận nhiều hostname tương đương của cùng realm.
    if not issuer_accepted(payload.get("iss")):
        return unauthorized("Invalid Bearer token")
    return jsonify(
        message="Secure resource OK",
        preferred_username=payload.get("preferred_username"),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False)
