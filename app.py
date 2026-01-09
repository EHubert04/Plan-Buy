from flask import Flask, render_template, request, jsonify
import os
from supabase import create_client, Client

app = Flask(__name__)

# -------------------------
# Supabase Client Helpers
# -------------------------

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")  # Backend-only secret!
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    return create_client(url, key)

def _data(res):
    return getattr(res, "data", None)

def _error(res):
    return getattr(res, "error", None)

def fetch_project(sb: Client, project_id: int):
    # 1) Project
    p_res = sb.table("projects").select("id,name").eq("id", project_id).limit(1).execute()
    if _error(p_res):
        raise RuntimeError(str(_error(p_res)))
    rows = _data(p_res) or []
    if not rows:
        return None
    project = rows[0]

    # 2) Todos (inkl. done + id)
    t_res = sb.table("todos").select("id,content,done").eq("project_id", project_id).order("id").execute()
    if _error(t_res):
        raise RuntimeError(str(_error(t_res)))
    todos = _data(t_res) or []

    # 3) Resources (inkl. purchased + id)
    r_res = sb.table("resources").select("id,name,quantity,purchased").eq("project_id", project_id).order("id").execute()
    if _error(r_res):
        raise RuntimeError(str(_error(r_res)))
    resources = _data(r_res) or []

    # Defaults, falls quantity null ist
    for r in resources:
        if r.get("quantity") is None:
            r["quantity"] = 1

    return {
        "id": project["id"],
        "name": project["name"],
        "todos": todos,         # jetzt Objekte!
        "resources": resources  # jetzt Objekte inkl. purchased
    }

def fetch_all_projects(sb: Client):
    p_res = sb.table("projects").select("id,name").order("id").execute()
    if _error(p_res):
        raise RuntimeError(str(_error(p_res)))
    projects = _data(p_res) or []
    if not projects:
        return []

    ids = [p["id"] for p in projects]

    t_res = sb.table("todos").select("project_id,id,content,done").in_("project_id", ids).execute()
    if _error(t_res):
        raise RuntimeError(str(_error(t_res)))
    todos_rows = _data(t_res) or []

    r_res = sb.table("resources").select("project_id,id,name,quantity,purchased").in_("project_id", ids).execute()
    if _error(r_res):
        raise RuntimeError(str(_error(r_res)))
    resources_rows = _data(r_res) or []

    todos_by_pid = {}
    for row in todos_rows:
        todos_by_pid.setdefault(row["project_id"], []).append({
            "id": row["id"],
            "content": row["content"],
            "done": row.get("done", False)
        })

    resources_by_pid = {}
    for row in resources_rows:
        resources_by_pid.setdefault(row["project_id"], []).append({
            "id": row["id"],
            "name": row["name"],
            "quantity": row.get("quantity") if row.get("quantity") is not None else 1,
            "purchased": row.get("purchased", False)
        })

    result = []
    for p in projects:
        pid = p["id"]
        result.append({
            "id": pid,
            "name": p["name"],
            "todos": todos_by_pid.get(pid, []),
            "resources": resources_by_pid.get(pid, [])
        })
    return result

# -------------------------
# Routes
# -------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/health/app")
def health_app():
    return {"ok": True}, 200

@app.get("/health/db")
def health_db():
    try:
        sb = get_supabase()
        # Minimal "Ping": eine harmlose Query
        res = sb.table("projects").select("id").limit(1).execute()
        if _error(res):
            return {"ok": False, "error": str(_error(res))}, 500
        return {"ok": True, "db": "reachable"}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

# Alle Projekte abrufen
@app.route("/api/projects", methods=["GET"])
def get_projects():
    try:
        sb = get_supabase()
        return jsonify(fetch_all_projects(sb))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Neues Projekt erstellen
@app.route("/api/projects", methods=["POST"])
def add_project():
    try:
        sb = get_supabase()
        data = request.get_json(force=True)
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400

        ins = sb.table("projects").insert({"name": name}).execute()
        if _error(ins):
            return jsonify({"error": str(_error(ins))}), 500

        created = (_data(ins) or [])[0]
        return jsonify({"id": created["id"], "name": created["name"], "todos": [], "resources": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Item (Todo oder Ressource) zu Projekt hinzufügen
@app.route("/api/projects/<int:p_id>/items", methods=["POST"])
def add_item(p_id):
    try:
        sb = get_supabase()
        data = request.get_json(force=True)

        item_type = data.get("type")  # "todo" oder "resource"
        content = (data.get("content") or "").strip()

        if item_type not in ("todo", "resource"):
            return jsonify({"error": "type must be 'todo' or 'resource'"}), 400
        if not content:
            return jsonify({"error": "content is required"}), 400

        # Check project exists
        existing = fetch_project(sb, p_id)
        if not existing:
            return jsonify({"error": f"project {p_id} not found"}), 404

        if item_type == "todo":
            res = sb.table("todos").insert({"project_id": p_id, "content": content,"done":False}).execute()
        else:
            quantity = data.get("quantity", 1)
            # quantity robust machen
            try:
                quantity = int(quantity)
            except Exception:
                quantity = 1
            if quantity < 1:
                quantity = 1

            res = sb.table("resources").insert({"project_id": p_id, "name": content, "quantity": quantity,"purchased":False}).execute()

        if _error(res):
            return jsonify({"error": str(_error(res))}), 500

        # Return updated project
        updated = fetch_project(sb, p_id)
        return jsonify(updated)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/api/projects/<int:p_id>/todos/<int:todo_id>", methods=["PATCH"])
def update_todo(p_id, todo_id):
    try:
        sb = get_supabase()
        data = request.get_json(force=True)

        if "done" not in data:
            return jsonify({"error": "missing 'done'"}), 400

        done = bool(data["done"])

        res = sb.table("todos") \
            .update({"done": done}) \
            .eq("id", todo_id) \
            .eq("project_id", p_id) \
            .execute()

        if _error(res):
            return jsonify({"error": str(_error(res))}), 500

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects/<int:p_id>/resources/<int:res_id>", methods=["PATCH"])
def update_resource(p_id, res_id):
    try:
        sb = get_supabase()
        data = request.get_json(force=True)

        patch = {}

        if "purchased" in data:
            patch["purchased"] = bool(data["purchased"])

        if "quantity" in data:
            try:
                q = int(data["quantity"])
            except Exception:
                return jsonify({"error": "quantity must be an integer"}), 400
            if q < 1:
                q = 1
            patch["quantity"] = q

        if not patch:
            return jsonify({"error": "nothing to update"}), 400

        res = sb.table("resources") \
            .update(patch) \
            .eq("id", res_id) \
            .eq("project_id", p_id) \
            .execute()

        if _error(res):
            return jsonify({"error": str(_error(res))}), 500

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)