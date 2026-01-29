import os
import sys
from huggingface_hub import InferenceClient

# Konfiguration
MODEL_ID = "vicgalle/xlm-roberta-large-xnli-anli"
HF_TOKEN = os.environ.get("HF_TOKEN") 

def get_db_categories(sb):
    """Lädt Kategorien und Keywords aus der Datenbank."""
    try:
        res = sb.table("resource_categories").select("id, name, keywords").execute()
        rows = getattr(res, "data", []) or []
        parsed_rows = []
        for r in rows:
            raw_kw = r.get("keywords") or ""
            kw_list = [k.strip().lower() for k in raw_kw.split(",") if k.strip()] if raw_kw else []
            parsed_rows.append({"id": r["id"], "name": r["name"], "keywords": kw_list})
        return parsed_rows
    except Exception:
        return []

def get_ai_category_name(valid_categories_names, item_name):
    """Nutzt KI via Hugging Face, um einen Namen einer Kategorie zuzuordnen."""
    if not HF_TOKEN:
        return None
    
    client = InferenceClient(model=MODEL_ID, token=HF_TOKEN)

    try:
        result = client.zero_shot_classification(
            text=item_name,
            candidate_labels=valid_categories_names, 
            multi_label=False
        )
        
        best_label = None
        best_score = 0.0

        # Robustes Parsing der API-Antwort
        if hasattr(result, "labels") and hasattr(result, "scores"):
            best_label = result.labels[0]
            best_score = result.scores[0]
        elif isinstance(result, dict) and "labels" in result:
            best_label = result["labels"][0]
            best_score = result["scores"][0]
        elif isinstance(result, list) and len(result) > 0:
             first = result[0]
             best_label = first.get("label") if isinstance(first, dict) else getattr(first, "label", None)
             best_score = first.get("score") if isinstance(first, dict) else getattr(first, "score", 0.0)

        # Schwellenwert für die Zuordnung
        if best_label and best_score > 0.4:
            return best_label
        
        return None

    except Exception:
        return None

def get_category_id_for_item(sb, name):
    """Hauptfunktion zur Bestimmung der Kategorie-ID (Cache -> Keywords -> KI)."""
    if not name: 
        return None
    
    name_clean = name.lower().strip()

    # 1. Cache-Abfrage
    try:
        res = sb.table("categorization_cache").select("category_id").eq("keyword", name_clean).execute()
        if res.data and res.data[0]['category_id']:
            return res.data[0]['category_id']
    except Exception: 
        pass

    all_categories = get_db_categories(sb)
    if not all_categories: 
        return None 

    # 2. Keyword-Matching
    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            _update_cache(sb, name_clean, cat["name"], cat["id"])
            return cat["id"]

    # 3. KI-Klassifizierung
    label_map = {cat['name']: cat for cat in all_categories}
    candidate_labels = list(label_map.keys())
    found_category_name = get_ai_category_name(candidate_labels, name)

    if found_category_name:
        matched_cat = label_map.get(found_category_name)
        if matched_cat:
            _update_cache(sb, name_clean, matched_cat["name"], matched_cat["id"])
            return matched_cat["id"]

    # Fallback: "Sonstiges"
    for cat in all_categories:
        if cat["name"].lower() == "sonstiges":
            return cat["id"]

    return None

def _update_cache(sb, keyword, cat_name, cat_id):
    """Hilfsfunktion zum Aktualisieren des Caches."""
    try:
        sb.table("categorization_cache").upsert({
            "keyword": keyword, 
            "category": cat_name, 
            "category_id": cat_id
        }).execute()
    except Exception:
        pass