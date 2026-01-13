from flask import request, abort
from supabase_utils import get_supabase_public


def require_user_id() -> str:
    """Reads Authorization: Bearer <JWT> and returns user id, otherwise abort(401)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(401)

    jwt = auth_header.split(" ", 1)[1].strip()
    if not jwt:
        abort(401)

    try:
        sb_public = get_supabase_public()
        resp = sb_public.auth.get_user(jwt)

        user = getattr(resp, "user", None)
        if user and getattr(user, "id", None):
            return user.id

        d = resp.model_dump() if hasattr(resp, "model_dump") else (resp.dict() if hasattr(resp, "dict") else {})
        uid = (d.get("user") or {}).get("id")
        if not uid:
            abort(401)
        return uid
    except Exception:
        abort(401)
