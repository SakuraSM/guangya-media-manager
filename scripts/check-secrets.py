#!/usr/bin/env python3
"""Fail when tracked Git history contains likely credentials or public author emails."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

MAX_BLOB_BYTES = 10 * 1024 * 1024
ENV_LIKE_SUFFIXES = {".conf", ".env", ".ini", ".json", ".md", ".toml", ".txt", ".yaml", ".yml"}
SENSITIVE_NAMES = (
    b"ADMIN_PASSWORD",
    b"AI_API_KEY",
    b"API_KEY",
    b"ACCESS_TOKEN",
    b"CLIENT_SECRET",
    b"PASSWORD",
    b"PRIVATE_KEY",
    b"REFRESH_TOKEN",
    b"SESSION_SECRET",
    b"TMDB_API_TOKEN",
    b"TOKEN",
    b"TOKEN_ENCRYPTION_KEY",
)
PLACEHOLDER_MARKERS = (
    b"change-me",
    b"demo",
    b"example",
    b"media_manager",
    b"placeholder",
    b"random",
    b"replace",
    b"test",
    b"your",
    "你的".encode(),
    "替换".encode(),
    "至少".encode(),
)
KNOWN_SECRET_PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:DSA |EC |OPENSSH |PGP |RSA )?PRIVATE KEY-----"),
    "github-token": re.compile(
        rb"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{20,})\b"
    ),
    "aws-access-key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "openai-key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "google-api-key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "jwt": re.compile(
        rb"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
    ),
}
QUOTED_ASSIGNMENT = re.compile(
    rb"(?im)^\s*([A-Z][A-Z0-9_-]*(?:KEY|PASSWORD|SECRET|TOKEN)[A-Z0-9_-]*)"
    rb"[ \t]*[:=][ \t]*['\"]([^'\"]{8,})['\"]"
)
UNQUOTED_ASSIGNMENT = re.compile(
    rb"(?im)^\s*([A-Z][A-Z0-9_-]*(?:KEY|PASSWORD|SECRET|TOKEN)[A-Z0-9_-]*)"
    rb"[ \t]*[:=][ \t]*([^\s#]{8,})[ \t]*$"
)


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], stderr=subprocess.DEVNULL)


def fingerprint(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()[:12]


def is_github_noreply(email: str) -> bool:
    normalized = email.casefold()
    return normalized == "noreply@github.com" or normalized.endswith(
        "@users.noreply.github.com"
    )


def public_revisions() -> list[str]:
    return git("rev-list", "--branches", "--tags", "--remotes=origin").decode().splitlines()


def is_placeholder(value: bytes) -> bool:
    normalized = value.strip().strip(b"'\"").lower()
    return not normalized or any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def paths_by_blob() -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for revision in public_revisions():
        tree = git("ls-tree", "-r", "--full-tree", revision).decode("utf-8", "replace")
        for entry in tree.splitlines():
            metadata, path = entry.split("\t", 1)
            _mode, kind, object_id = metadata.split()
            if kind == "blob":
                result[object_id].add(path)
    return result


def scan_blob(path: str, content: bytes) -> list[tuple[str, bytes]]:
    findings: list[tuple[str, bytes]] = []
    for category, pattern in KNOWN_SECRET_PATTERNS.items():
        findings.extend((category, match.group(0)) for match in pattern.finditer(content))

    assignment_patterns = [QUOTED_ASSIGNMENT]
    if Path(path).suffix.casefold() in ENV_LIKE_SUFFIXES or Path(path).name.startswith(".env"):
        assignment_patterns.append(UNQUOTED_ASSIGNMENT)
    for pattern in assignment_patterns:
        for match in pattern.finditer(content):
            name, value = match.groups()
            if any(
                sensitive_name in name.upper() for sensitive_name in SENSITIVE_NAMES
            ) and not is_placeholder(value):
                findings.append(("credential-assignment", value))
    return findings


def scan_commit_emails() -> list[str]:
    findings: list[str] = []
    rows = git(
        "log",
        "--format=%H%x09%ae%x09%ce",
        "--branches",
        "--tags",
        "--remotes=origin",
    ).decode().splitlines()
    for row in rows:
        revision, author_email, committer_email = row.split("\t")
        for role, email in (("author", author_email), ("committer", committer_email)):
            if email and not is_github_noreply(email):
                findings.append(
                    f"public-commit-email\tcommit={revision[:12]}\trole={role}"
                    f"\tfingerprint={fingerprint(email.encode())}"
                )
    return findings


def main() -> int:
    findings: set[str] = set(scan_commit_emails())
    blobs = paths_by_blob()
    for object_id, paths in blobs.items():
        content = git("cat-file", "blob", object_id)
        if len(content) > MAX_BLOB_BYTES or b"\x00" in content[:8192]:
            continue
        for path in sorted(paths):
            for category, value in scan_blob(path, content):
                findings.add(
                    f"{category}\tpath={path}\tblob={object_id[:12]}"
                    f"\tfingerprint={fingerprint(value)}\tlength={len(value)}"
                )

    if findings:
        print("Potential secrets or privacy-sensitive commit metadata found:", file=sys.stderr)
        for finding in sorted(findings):
            print(f"- {finding}", file=sys.stderr)
        print("Values are intentionally redacted. Remove or rotate them before publishing.", file=sys.stderr)
        return 1

    print(f"Secret scan passed: {len(blobs)} unique historical blobs inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
