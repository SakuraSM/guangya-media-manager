import os
from pathlib import Path

TEST_DATABASE_FILE = Path(__file__).parents[1] / "test-media-manager.db"
TEST_DATABASE_FILE.unlink(missing_ok=True)

os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{TEST_DATABASE_FILE}",
)
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("ADMIN_PASSWORD", "change-me")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-with-at-least-32-characters")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "")
