from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException
from supabase_utils import get_supabase_admin, error
from auth_utils import require_user_id
from repo import (
    fetch_projects_for_user,
    create_project,
    add_item,
    update_todo,
    update_resource,
)

api_bp = Blueprint("api", __name__)


@api_bp.get("/health/app")
def health_app():
    return {"ok": True}, 200


@api_bp.get("/health/db")
def health_db():
    try:
        sb = get_supabase_admin()
        res = sb.table("projects").select("id").limit(1).execute()
        if error(res):
            return {"ok": False, "error": str(error(res))}, 500
        return {"ok": True, "db": "reachable"}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


@api_bp.get("/api/projects")
def get_projects():
    try:
        user_id = require_user_id()
        sb = get_supabase_admin()
        return jsonify(fetch_projects_for_user(sb, user_id))
    except HTTPException as e:
        return jsonify({"error": "unauthorized"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/api/projects")
def add_project_route():
    try:
        user_id = require_user_id()
        sb = get_supabase_admin()

        body = request.get_json(force=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400

        return jsonify(create_project(sb, user_id, name))
    except HTTPException as e:
        return jsonify({"error": "unauthorized"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.post("/api/projects/<int:p_id>/items")
def add_item_route(p_id: int):
    try:
        user_id = require_user_id()
        sb = get_supabase_admin()

        body = request.get_json(force=True) or {}
        item_type = body.get("type")
        content = (body.get("content") or "").strip()

        if item_type not in ("todo", "resource"):
            return jsonify({"error": "type must be 'todo' or 'resource'"}), 400
        if not content:
            return jsonify({"error": "content is required"}), 400

        qty = body.get("quantity", 1)
        try:
            qty = int(qty)
        except Exception:
            qty = 1
        if qty < 1:
            qty = 1

        updated = add_item(sb, p_id, user_id, item_type, content, quantity=qty)
        if not updated:
            return jsonify({"error": f"project {p_id} not found"}), 404
        return jsonify(updated)
    except HTTPException as e:
        return jsonify({"error": "unauthorized"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.patch("/api/projects/<int:p_id>/todos/<int:todo_id>")
def update_todo_route(p_id: int, todo_id: int):
    try:
        user_id = require_user_id()
        sb = get_supabase_admin()

        body = request.get_json(force=True) or {}
        if "done" not in body:
            return jsonify({"error": "missing 'done'"}), 400

        ok = update_todo(sb, p_id, user_id, todo_id, bool(body["done"]))
        if not ok:
            return jsonify({"error": "not found"}), 404
        return jsonify({"status": "success"})
    except HTTPException as e:
        return jsonify({"error": "unauthorized"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.patch("/api/projects/<int:p_id>/resources/<int:res_id>")
def update_resource_route(p_id: int, res_id: int):
    try:
        user_id = require_user_id()
        sb = get_supabase_admin()

        body = request.get_json(force=True) or {}
        purchased = body.get("purchased", None)
        quantity = body.get("quantity", None)

        ok = update_resource(sb, p_id, user_id, res_id, purchased=purchased, quantity=quantity)
        if not ok:
            return jsonify({"error": "not found"}), 404
        return jsonify({"status": "success"})
    except HTTPException as e:
        return jsonify({"error": "unauthorized"}), e.code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
