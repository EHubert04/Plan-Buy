import os
import sys
from huggingface_hub import InferenceClient

# Wir nutzen wieder den Hugging Face Token
HF_TOKEN = os.environ.get("HF_TOKEN")

# Spezielles Modell für "Ordne X in Kategorien A, B, C ein"
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
        sys.stderr.write(f"DEBUG: Starte Zero-Shot für '{item_name}'...\n")
        
        # Der offizielle Client kümmert sich um URLs und Header
        client = InferenceClient(token=HF_TOKEN)
        
        # Die Magie: Wir werfen das Item und die Kategorien direkt rein
        # Die KI berechnet Wahrscheinlichkeiten für jede Kategorie
        result = client.zero_shot_classification(
            item_name,
            valid_categories_names,
            model=MODEL_ID
        )
        
        # Das Ergebnis ist sortiert nach Wahrscheinlichkeit (höchste zuerst)
        # Struktur: {'labels': ['Obst', 'Werkzeug'], 'scores': [0.95, 0.05], ...}
        best_label = result['labels'][0]
        best_score = result['scores'][0]
        
        sys.stderr.write(f"DEBUG: KI Ergebnis: '{best_label}' ({best_score:.2f})\n")
        
        # Optional: Nur akzeptieren, wenn die KI sich halbwegs sicher ist (> 20%)
        if best_score > 0.2:
            return best_label
        else:
            sys.stderr.write(f"DEBUG: KI unsicher ({best_score:.2f}), überspringe.\n")

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