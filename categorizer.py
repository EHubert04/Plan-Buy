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

def get_ai_category_name(valid_categories_names, item_name):
    if not HF_TOKEN:
        sys.stderr.write("DEBUG: KI übersprungen (Kein HF_TOKEN)\n")
        return None
    
    # Client initialisieren (Modell wird hier definiert)
    client = InferenceClient(model=MODEL_ID, token=HF_TOKEN)

    try:
        sys.stderr.write(f"DEBUG: Sende Zero-Shot Anfrage via Library für '{item_name}'...\n")
        
        # Die Library hat eine spezielle Methode für Zero-Shot
        # Wir übergeben den Text und die Labels (Kategorien)
        result = client.zero_shot_classification(
            text=item_name,
            labels=valid_categories_names,
            multi_label=False
        )
        
        best_match = result[0] # Das beste Ergebnis steht an erster Stelle
        best_label = best_match.label if hasattr(best_match, 'label') else best_match['label']
        best_score = best_match.score if hasattr(best_match, 'score') else best_match['score']

        sys.stderr.write(f"DEBUG: KI Ergebnis: '{best_label}' ({best_score:.2f})\n")

        if best_score > 0.2:
            return best_label
        
        return None

    except Exception as e:
        sys.stderr.write(f"!!! KI CRASH (HuggingFace Hub): {e}\n")
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