import os
import sys
from huggingface_hub import InferenceClient

HF_TOKEN = os.environ.get("HF_TOKEN")
MODEL_ID = "facebook/bart-large-mnli"

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

def get_ai_category_name(valid_categories_names, item_name):
    if not HF_TOKEN:
        sys.stderr.write("DEBUG: KI übersprungen (Kein HF_TOKEN)\n")
        return None
    
    try:
        sys.stderr.write(f"DEBUG: Starte Zero-Shot (BART) für '{item_name}'...\n")
        
        client = InferenceClient(model=MODEL_ID, token=HF_TOKEN)
        
        result = client.zero_shot_classification(
            item_name,
            valid_categories_names
        )
        
        # --- HIER IST DER FIX ---
        # Falls die API eine Liste zurückgibt (z.B. [{...}]), nehmen wir das erste Element.
        if isinstance(result, list):
            result = result[0]
            
        # Jetzt können wir sicher zugreifen (wir nutzen Dict-Zugriff [], das ist robuster)
        best_label = result['labels'][0]
        best_score = result['scores'][0]
        # ------------------------
        
        sys.stderr.write(f"DEBUG: KI Ergebnis: '{best_label}' ({best_score:.2f})\n")
        
        if best_score > 0.2:
            return best_label
        
    except Exception as e:
        sys.stderr.write(f"!!! KI CRASH (HuggingFace): {e}\n")
        
    return None

def get_category_id_for_item(sb, name):
    # (Dieser Teil bleibt exakt gleich wie vorher)
    if not name: return None
    name_clean = name.lower().strip()

    # 1. Cache
    try:
        res = sb.table("categorization_cache").select("category_id").eq("keyword", name_clean).execute()
        if res.data and res.data[0]['category_id']:
            sys.stderr.write(f"DEBUG: Cache Treffer für '{name_clean}' -> {res.data[0]['category_id']}\n")
            return res.data[0]['category_id']
    except Exception: pass

    all_categories = get_db_categories(sb)
    if not all_categories: return None 

    # 2. Keywords
    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            sys.stderr.write(f"DEBUG: Keyword Treffer für '{name_clean}' -> {cat['name']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                }).execute()
            except: pass
            return cat["id"]

    # 3. KI (Zero-Shot)
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

    # 4. Fallback
    for cat in all_categories:
        if cat["name"].lower() == "sonstiges":
            return cat["id"]

    return None