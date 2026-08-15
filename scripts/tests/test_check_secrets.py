from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "check-secrets.py"
SPEC = importlib.util.spec_from_file_location("check_secrets", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECK_SECRETS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK_SECRETS)


class GithubMergeMetadataTests(unittest.TestCase):
    def test_accepts_github_generated_merge(self) -> None:
        self.assertTrue(
            CHECK_SECRETS.is_github_generated_pull_request_commit(
                "parent-one parent-two",
                "GitHub",
                "noreply@github.com",
                "Merge pull request #15",
            )
        )

    def test_accepts_github_generated_squash_commit(self) -> None:
        self.assertTrue(
            CHECK_SECRETS.is_github_generated_pull_request_commit(
                "parent-one",
                "GitHub",
                "noreply@github.com",
                "Improve review state (#15)",
            )
        )

    def test_rejects_regular_github_commit_without_pull_request_suffix(self) -> None:
        self.assertFalse(
            CHECK_SECRETS.is_github_generated_pull_request_commit(
                "parent-one",
                "GitHub",
                "noreply@github.com",
                "Update README",
            )
        )

    def test_rejects_merge_from_regular_committer(self) -> None:
        self.assertFalse(
            CHECK_SECRETS.is_github_generated_pull_request_commit(
                "parent-one parent-two",
                "Developer",
                "developer@example.com",
                "Merge pull request #15",
            )
        )

    def test_rejects_spoofed_github_email(self) -> None:
        self.assertFalse(
            CHECK_SECRETS.is_github_generated_pull_request_commit(
                "parent-one parent-two",
                "Developer",
                "noreply@github.com",
                "Merge pull request #15",
            )
        )


if __name__ == "__main__":
    unittest.main()
