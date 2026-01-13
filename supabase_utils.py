import os
from supabase import create_client, Client


def get_supabase_admin() -> Client:
    """Server-only client (uses SUPABASE_SERVICE_ROLE_KEY / secret key)."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    return create_client(url, key)


def get_supabase_public() -> Client:
    """Public client (uses SUPABASE_PUBLISHABLE_KEY). Used for token verification."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY not set")
    return create_client(url, key)


def data(res):
    return getattr(res, "data", None)


def error(res):
    return getattr(res, "error", None)
