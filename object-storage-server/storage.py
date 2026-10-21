"""Prepare and verify the three MyMiniCloud lab buckets using the S3 API.

Run from any directory. Credentials follow the Compose lab defaults and can
be overridden using MINIO_ROOT_USER / MINIO_ROOT_PASSWORD.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

HERE = Path(__file__).resolve().parent
FILES = (
    ("demo", "index.html", HERE.parent / "web-frontend-server/html/index.html", "text/html"),
    ("profile-pics", "avatar.jpg", HERE / "sample-uploads/avatar.jpg", "image/jpeg"),
    ("documents", "baocao.pdf", HERE / "sample-uploads/baocao.pdf", "application/pdf"),
)
PUBLIC_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "PublicReadProfilePictures",
        "Effect": "Allow",
        "Principal": {"AWS": ["*"]},
        "Action": ["s3:GetObject"],
        "Resource": ["arn:aws:s3:::profile-pics/*"],
    }],
}


def client(endpoint):
    return boto3.client(
        "s3", endpoint_url=endpoint, region_name="us-east-1",
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=15,
                      retries={"max_attempts": 2}, s3={"addressing_style": "path"}),
    )


def missing(exc):
    return exc.response["Error"]["Code"] in {"404", "NoSuchBucket", "NoSuchKey", "NotFound"}


def policy(s3):
    try:
        s3.head_bucket(Bucket="profile-pics")
    except ClientError as exc:
        if missing(exc):
            raise RuntimeError("Create profile-pics in Console first, or run the seed command.") from exc
        raise
    s3.put_bucket_policy(Bucket="profile-pics", Policy=json.dumps(PUBLIC_POLICY))
    print("Configured profile-pics: anonymous GetObject only.")


def seed(s3, replace_files=False):
    # Check all source files before creating any buckets.
    for _, _, path, _ in FILES:
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"Missing or empty source file: {path}")
    for bucket, key, path, content_type in FILES:
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError as exc:
            if not missing(exc):
                raise
            s3.create_bucket(Bucket=bucket)
            print(f"Created bucket: {bucket}")
        exists = True
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if not missing(exc):
                raise
            exists = False
        if exists and not replace_files:
            print(f"Kept existing object: {bucket}/{key}")
            continue
        s3.put_object(Bucket=bucket, Key=key, Body=path.read_bytes(), ContentType=content_type)
        print(f"Uploaded: {bucket}/{key}")
    policy(s3)
    print("demo/documents retain their existing policies (new buckets are private).")


def anonymous(endpoint, path, method="GET", data=None):
    request = urllib.request.Request(endpoint.rstrip("/") + "/" + path, data=data, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def verify(s3, endpoint):
    failures = []

    def check(ok, label):
        print(f"{'PASS' if ok else 'FAIL'} {label}")
        if not ok:
            failures.append(label)

    for bucket, key, path, content_type in FILES:
        response = s3.get_object(Bucket=bucket, Key=key)
        with response["Body"] as stream:
            received = stream.read()
        check(hashlib.sha256(received).digest() == hashlib.sha256(path.read_bytes()).digest(),
              f"Authenticated download + SHA-256: {bucket}/{key}")
        check(response["ContentType"].split(";")[0] == content_type, f"Content-Type: {bucket}/{key}")
    status, body = anonymous(endpoint, "profile-pics/avatar.jpg")
    check(status == 200 and body == (HERE / "sample-uploads/avatar.jpg").read_bytes(),
          "Public avatar GET without credentials")
    for path in ("demo/index.html", "documents/baocao.pdf", "profile-pics?list-type=2"):
        status, _ = anonymous(endpoint, path)
        check(status == 403, f"Anonymous access denied: {path}")
    # Probe only a unique, disposable key; never test DELETE against the user's avatar.
    probe = f"access-test-{uuid.uuid4().hex}.txt"
    status, _ = anonymous(endpoint, f"profile-pics/{probe}", "PUT", b"permission probe")
    check(status == 403, "Anonymous PUT denied")
    if 200 <= status < 300:
        s3.delete_object(Bucket="profile-pics", Key=probe)
    status, _ = anonymous(endpoint, f"profile-pics/{probe}", "DELETE")
    check(status == 403, "Anonymous DELETE denied")
    saved_policy = json.loads(s3.get_bucket_policy(Bucket="profile-pics")["Policy"])
    statements = saved_policy.get("Statement", [])
    actions = [action for statement in statements for action in (
        statement.get("Action", []) if isinstance(statement.get("Action"), list)
        else [statement.get("Action")])]
    check(actions == ["s3:GetObject"], "Public policy grants only GetObject")
    if failures:
        raise RuntimeError(f"{len(failures)} storage checks failed.")
    print("All 13 storage checks passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seed", "policy", "verify"))
    parser.add_argument("--endpoint", default="http://localhost:9000", help="S3 API endpoint, not Console")
    parser.add_argument("--replace-files", action="store_true",
                        help="With seed, replace ONLY the three named lab objects from the local files")
    args = parser.parse_args()
    if args.replace_files and args.command != "seed":
        parser.error("--replace-files applies only to seed")
    if not args.endpoint.startswith(("http://", "https://")):
        parser.error("--endpoint must begin with http:// or https://")
    try:
        s3 = client(args.endpoint)
        if args.command == "seed":
            seed(s3, args.replace_files)
        elif args.command == "policy":
            policy(s3)
        else:
            verify(s3, args.endpoint)
    except (BotoCoreError, ClientError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
