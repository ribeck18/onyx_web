import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_env_var(var_name: str) -> str:
    """Returns the value from the env associated with the var_name"""
    value = os.environ.get(var_name)
    if value is None:
        raise RuntimeError(f"No env variable associated with {var_name}")

    return value


def get_optional_env_var(var_name: str, default: str = "") -> str:
    """Return an env var that is absent in local dev / tests, defaulting instead.

    Auth secrets (Entra client, session secret) are only populated on a real
    deployment; the test suite and a bare local checkout must still import the
    app, so these reads must not hard-fail the way get_env_var does.
    """
    value = os.environ.get(var_name)
    return value if value else default


def get_bool_env_var(var_name: str, default: bool = False) -> bool:
    """Read a truthy/falsy flag from the env (1/true/yes/on, case-insensitive)."""
    value = os.environ.get(var_name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


database_url = get_env_var("DATABASE_URL")

# The root directory under which uploaded files are stored on disk. Local
# testing points at a gitignored repo folder; production points outside the
# repo (e.g. its own server volume) so branch switches never touch uploads.
file_storage_root = Path(get_env_var("FILE_STORAGE_ROOT"))

# Gate SQL echo behind an env flag so production logs stay quiet and never leak
# query contents; local dev can opt in with SQL_ECHO=1.
sql_echo = get_bool_env_var("SQL_ECHO", False)

# --- Microsoft Entra SSO + app-owned sessions (ADR 0007) -----------------
# Single-tenant Entra OIDC. These are empty in local dev / tests (the SSO flow
# is exercised against a mocked identity seam, never the real directory) and are
# populated from the server .env on a real deployment.
tenant_id = get_optional_env_var("TENANT_ID")
client_id = get_optional_env_var("CLIENT_ID")
client_secret = get_optional_env_var("CLIENT_SECRET")

# Signs the short-lived OIDC handshake cookie (state / nonce / PKCE verifier).
# A weak default keeps local dev runnable; production must set a strong value.
session_secret = get_optional_env_var("SESSION_SECRET", "dev-insecure-session-secret-change-me")

# Break-glass admins: comma-separated emails always granted admin on login and
# upserted if missing. Stored normalized (lowercased) for case-insensitive match.
admin_emails: set[str] = {
    email.strip().lower()
    for email in get_optional_env_var("ONYX_ADMIN_EMAILS").split(",")
    if email.strip()
}

# Mark session cookies Secure in production (https); off for local http dev.
cookie_secure = get_bool_env_var("COOKIE_SECURE", False)

# Public base URL used to build the Entra redirect URI (/auth/callback).
app_base_url = get_optional_env_var("APP_BASE_URL", "http://localhost:8000").rstrip("/")
