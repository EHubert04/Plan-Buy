import os
import requests
import sys
import time
from huggingface_hub import InferenceClient

# Wir nutzen das Zero-Shot Modell via Router
MODEL_ID = "facebook/bart-large-mnli"
HF_API_URL = f"https://router.huggingface.co/models/{MODEL_ID}"
HF_TOKEN = os.environ.get("HF_TOKEN") 
def get_db_categories(sb):
    # (Dieser Teil bleibt unverändert)
    try:
        res = sb.table("resource_categories").select("id, name, keywords").execute()
        rows = getattr(res, "data", []) or []
        parsed_rows = []
        for r in rows:
            raw_kw = r.get("keywords") or ""
            kw_list = [k.strip().lower() for k in raw_kw.split(",") if k.strip()] if raw_kw else []
            parsed_rows.append({"id": r["id"], "name": r["name"], "keywords": kw_list})
        return parsed_rows
    except Exception as e:
        sys.stderr.write(f"!!! DB LOAD ERROR: {e}\n")
        return []

def get_category_id_for_item(sb, name):
    if not name: return None
    name_clean = name.lower().strip()

    # 1. Cache prüfen (bleibt gleich)
    try:
        res = sb.table("categorization_cache").select("category_id").eq("keyword", name_clean).execute()
        if res.data and res.data[0]['category_id']:
            sys.stderr.write(f"DEBUG: Cache Treffer für '{name_clean}' -> {res.data[0]['category_id']}\n")
            return res.data[0]['category_id']
    except Exception: pass

    all_categories = get_db_categories(sb)
    if not all_categories: return None 

    # 2. Exakter Keyword-Match (bleibt gleich - fängt das Offensichtliche ab)
    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            sys.stderr.write(f"DEBUG: Keyword Treffer für '{name_clean}' -> {cat['name']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                }).execute()
            except: pass
            return cat["id"]

    # 3. KI Anfrage VORBEREITEN: Labels mit Keywords anreichern
    # Wir bauen eine Map: "Erweiterter Name" -> "Original Kategorie Objekt"
    label_map = {}
    candidate_labels = []

    for cat in all_categories:
        # Wir nehmen die ersten 5 Keywords als Kontext dazu, damit der String nicht zu lang wird
        # Format: "Kategoriename (Keyword1, Keyword2, ...)"
        keywords = cat.get("keywords", [])
        if keywords:
            # Nur die ersten 5, um Token zu sparen und Fokus zu behalten
            context_str = ", ".join(keywords[:5])
            extended_name = f"{cat['name']} ({context_str})"
        else:
            extended_name = cat["name"]
        
        candidate_labels.append(extended_name)
        label_map[extended_name] = cat # Speichern, um später ID wiederzufinden

    # 4. KI Fragen (mit den erweiterten Namen)
    found_extended_name = get_ai_category_name(candidate_labels, name)

    if found_extended_name:
        # 5. Rückauflösung: Welcher Kategorie gehört dieser erweiterte Name?
        matched_cat = label_map.get(found_extended_name)
        
        if matched_cat:
            sys.stderr.write(f"DEBUG: KI Mapping '{found_extended_name}' -> ID {matched_cat['id']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, 
                    "category": matched_cat["name"], # Originaler kurzer Name für Cache/DB
                    "category_id": matched_cat["id"]
                }).execute()
            except: pass
            return matched_cat["id"]

    # Fallback: Sonstiges
    for cat in all_categories:
        if cat["name"].lower() == "sonstiges":
            return cat["id"]

    return None
def get_category_id_for_item(sb, name):
    # (Dieser Teil bleibt exakt gleich wie vorher)
    if not name: return None
    name_clean = name.lower().strip()

    try:
        res = sb.table("categorization_cache").select("category_id").eq("keyword", name_clean).execute()
        if res.data and res.data[0]['category_id']:
            sys.stderr.write(f"DEBUG: Cache Treffer für '{name_clean}' -> {res.data[0]['category_id']}\n")
            return res.data[0]['category_id']
    except Exception: pass

    all_categories = get_db_categories(sb)
    if not all_categories: return None 

    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            sys.stderr.write(f"DEBUG: Keyword Treffer für '{name_clean}' -> {cat['name']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                }).execute()
            except: pass
            return cat["id"]

    valid_names = [c["name"] for c in all_categories]
    found_name = get_ai_category_name(valid_names, name)

    if found_name:
        for cat in all_categories:
            if cat["name"].lower() == found_name.lower():
                try:
                    sb.table("categorization_cache").upsert({
                        "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                    }).execute()
                except: pass
                return cat["id"]

    for cat in all_categories:
        if cat["name"].lower() == "sonstiges":
            return cat["id"]

    return None