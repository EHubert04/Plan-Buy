from typing import Dict, List, Optional
from supabase import Client
from supabase_utils import data, error
from categorizer import get_category_id_for_item

def _pid(v):
    try:
        return int(v)
    except Exception:
        return v

def ensure_project_owned(sb: Client, project_id: int, user_id: str) -> bool:
    res = (
        sb.table("projects")
        .select("id")
        .eq("id", project_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if error(res):
        raise RuntimeError(str(error(res)))
    return bool(data(res) or [])

def ensure_project_access(sb: Client, project_id: int, user_id: str) -> bool:
    """Owner ODER Member dürfen zugreifen."""
    if ensure_project_owned(sb, project_id, user_id):
        return True

    res = (
        sb.table("project_members")
        .select("project_id")
        .eq("project_id", project_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if error(res):
        raise RuntimeError(str(error(res)))
    return bool(data(res) or [])

def _attach_category_names(sb: Client, resources_rows: List[Dict]) -> None:
    cat_ids = sorted({r.get("category_id") for r in resources_rows if r.get("category_id")})
    if not cat_ids:
        for r in resources_rows:
            r["category"] = None
        return

    cats = sb.table("resource_categories").select("id,name").in_("id", cat_ids).execute()
    if error(cats):
        raise RuntimeError(str(error(cats)))
    cat_map = {c["id"]: c["name"] for c in (data(cats) or [])}

    for r in resources_rows:
        r["category"] = cat_map.get(r.get("category_id"))

def fetch_projects_for_user(sb: Client, user_id: str) -> List[Dict]:
    # 1) Eigene Projekte
    owned_res = sb.table("projects").select("id,name").eq("user_id", user_id).order("id").execute()
    if error(owned_res):
        raise RuntimeError(str(error(owned_res)))
    owned_projects = data(owned_res) or []

    # 2) Projekte, bei denen der User Mitglied ist
    mem_res = sb.table("project_members").select("project_id,role").eq("user_id", user_id).execute()
    if error(mem_res):
        raise RuntimeError(str(error(mem_res)))
    memberships = data(mem_res) or []
    shared_ids = [m["project_id"] for m in memberships if m.get("project_id") is not None]

    shared_projects = []
    if shared_ids:
        shared_res = sb.table("projects").select("id,name").in_("id", shared_ids).order("id").execute()
        if error(shared_res):
            raise RuntimeError(str(error(shared_res)))
        shared_projects = data(shared_res) or []

    # 3) Zusammenführen ohne Duplikate
    projects_map = {p["id"]: p for p in owned_projects}
    for p in shared_projects:
        projects_map.setdefault(p["id"], p)

    projects = list(projects_map.values())
    if not projects:
        return []

    ids = [p["id"] for p in projects]

    t_res = sb.table("todos").select("project_id,id,content,done").in_("project_id", ids).execute()
    r_res = sb.table("resources").select("project_id,id,name,quantity,purchased,category_id").in_("project_id", ids).execute()
    
    if error(t_res) or error(r_res):
        raise RuntimeError("Fehler beim Abrufen der Projektdaten")

    todos_rows = data(t_res) or []
    resources = data(r_res) or []
    
    _attach_category_names(sb, resources)

    try:
        _attach_category_names(sb, resources)
    except Exception:
        pass

    todos_by_pid: Dict[int, List[Dict]] = {}
    for row in todos_rows:
        pid = _pid(row["project_id"])
        todos_by_pid.setdefault(pid, []).append({
            "id": row["id"],
            "content": row["content"],
            "done": row.get("done", False),
        })

    resources_by_pid: Dict[int, List[Dict]] = {}
    for row in resources:
        pid = _pid(row["project_id"])
        resources_by_pid.setdefault(pid, []).append({
            "id": row["id"],
            "name": row["name"],
            "quantity": row.get("quantity") or 1,
            "purchased": row.get("purchased", False),
            "category": row.get("category"),
            "category": row.get("category"),
        })

    for pid in resources_by_pid:
        resources_by_pid[pid].sort(key=lambda x: (x.get("category") or "zzz", x.get("name") or ""))

    return [{
        "id": p["id"],
        "name": p["name"],
        "todos": todos_by_pid.get(_pid(p["id"]), []),
        "resources": resources_by_pid.get(_pid(p["id"]), []),
    } for p in projects]

def fetch_project_for_user(sb: Client, project_id: int, user_id: str) -> Optional[Dict]:
    if not ensure_project_access(sb, project_id, user_id):
        return None

    p_res = sb.table("projects").select("id,name").eq("id", project_id).limit(1).execute()
    t_res = sb.table("todos").select("id,content,done").eq("project_id", project_id).order("id").execute()
    r_res = sb.table("resources").select("id,name,quantity,purchased,category_id").eq("project_id", project_id).order("id").execute()
    
    if error(p_res) or error(t_res) or error(r_res):
        raise RuntimeError("Fehler beim Laden des Projekts")

    project = (data(p_res) or [None])[0]
    if not project: return None

    resources = data(r_res) or []
    _attach_category_names(sb, resources)
    resources.sort(key=lambda x: (x.get("category") or "zzz", x.get("name") or ""))

    for r in resources:
        if r.get("quantity") is None: r["quantity"] = 1

    return {
        "id": project["id"], 
        "name": project["name"], 
        "todos": data(t_res) or [], 
        "resources": resources
    }

def create_project(sb: Client, user_id: str, name: str) -> Dict:
    ins = sb.table("projects").insert({"name": name, "user_id": user_id}).execute()
    if error(ins):
        raise RuntimeError(str(error(ins)))
    created = (data(ins) or [])[0]
    return {"id": created["id"], "name": created["name"], "todos": [], "resources": []}

def add_item(sb: Client, project_id: int, user_id: str, item_type: str, content: str, quantity: int = 1) -> Optional[Dict]:
    if not ensure_project_access(sb, project_id, user_id):
        return None

    if item_type == "todo":
        res = sb.table("todos").insert({"project_id": project_id, "content": content, "done": False}).execute()
    else:
        cat_id = get_category_id_for_item(sb, content)
        payload = {
            "project_id": project_id,
            "name": content,
            "quantity": max(1, quantity),
            "purchased": False,
            "category_id": cat_id
        }
        res = sb.table("resources").insert(payload).execute()

    if error(res):
        raise RuntimeError(str(error(res)))

    return fetch_project_for_user(sb, project_id, user_id)

def update_todo(sb: Client, project_id: int, user_id: str, todo_id: int, done: bool) -> bool:
    if not ensure_project_access(sb, project_id, user_id):
        return False

    res = sb.table("todos").update({"done": bool(done)}).eq("id", todo_id).eq("project_id", project_id).execute()
    return bool(data(res))

def update_resource(sb: Client, project_id: int, user_id: str, res_id: int, **kwargs) -> bool:
    if not ensure_project_owned(sb, project_id, user_id):

def update_resource(sb: Client, project_id: int, user_id: str, res_id: int, purchased: Optional[bool] = None, quantity: Optional[int] = None, category_id: Optional[int] = None) -> bool:
    if not ensure_project_access(sb, project_id, user_id):
        return False

    patch = {k: v for k, v in kwargs.items() if v is not None}
    if "quantity" in patch:
        patch["quantity"] = max(1, int(patch["quantity"]))

    if not patch: return True

    res = sb.table("resources").update(patch).eq("id", res_id).eq("project_id", project_id).execute()
    
    # Automatisches Lernen für den Cache bei manueller Kategoriewahl
    if "category_id" in patch and data(res):
        try:
            item_name = data(res)[0]["name"]
            cat_res = sb.table("resource_categories").select("name").eq("id", patch["category_id"]).single().execute()
            if data(cat_res):
                sb.table("categorization_cache").upsert({
                    "keyword": item_name.lower().strip(),
                    "category": data(cat_res)["name"],
                    "category_id": patch["category_id"]
                }).execute()
        except Exception:
            pass

    return bool(data(res))

def delete_todo(sb: Client, project_id: int, user_id: str, todo_id: int) -> bool:
    if not ensure_project_owned(sb, project_id, user_id): return False
    if not ensure_project_access(sb, project_id, user_id):
        return False
    res = sb.table("todos").delete().eq("id", todo_id).eq("project_id", project_id).execute()
    return bool(data(res))

def delete_resource(sb: Client, project_id: int, user_id: str, res_id: int) -> bool:
    if not ensure_project_owned(sb, project_id, user_id): return False
    if not ensure_project_access(sb, project_id, user_id):
        return False
    res = sb.table("resources").delete().eq("id", res_id).eq("project_id", project_id).execute()
    return bool(data(res))

def _extract_users_from_admin_list(resp):
    if hasattr(resp, "users"):
        return resp.users or []
    if isinstance(resp, dict) and "users" in resp:
        return resp.get("users") or []
    if hasattr(resp, "data") and isinstance(resp.data, dict) and "users" in resp.data:
        return resp.data.get("users") or []
    if hasattr(resp, "data") and isinstance(resp.data, list):
        return resp.data
    return []

def find_user_id_by_email(sb: Client, email: str) -> Optional[str]:
    target = (email or "").strip().lower()
    if not target:
        return None

    page = 1
    per_page = 1000
    while True:
        resp = sb.auth.admin.list_users(page=page, per_page=per_page)
        users = _extract_users_from_admin_list(resp)

        for u in users:
            u_email = (u.get("email") if isinstance(u, dict) else getattr(u, "email", "")) or ""
            if u_email.strip().lower() == target:
                return u.get("id") if isinstance(u, dict) else getattr(u, "id", None)

        if len(users) < per_page:
            break
        page += 1

    return None

def add_project_member_by_email(sb: Client, project_id: int, owner_user_id: str, email: str, role: str = "editor") -> Dict:
    # Nur Owner darf einladen
    if not ensure_project_owned(sb, project_id, owner_user_id):
        raise PermissionError("Only the project owner can invite members")

    member_user_id = find_user_id_by_email(sb, email)
    if not member_user_id:
        raise ValueError("User with this email not found")

    res = sb.table("project_members").upsert({
        "project_id": project_id,
        "user_id": member_user_id,
        "role": role
    }).execute()
    if error(res):
        raise RuntimeError(str(error(res)))

    return {"project_id": project_id, "user_id": member_user_id, "role": role}