import os
import requests
import sys
import time
from huggingface_hub import InferenceClient

# Wir nutzen das Zero-Shot Modell via Router
MODEL_ID = "vicgalle/xlm-roberta-large-xnli-anli"
HF_API_URL = f"https://router.huggingface.co/models/{MODEL_ID}"
HF_TOKEN = os.environ.get("HF_TOKEN") 

def get_db_categories(sb):
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
    
    client = InferenceClient(model=MODEL_ID, token=HF_TOKEN)

    try:
        sys.stderr.write(f"DEBUG: Sende Zero-Shot Anfrage via Library für '{item_name}'...\n")
        
        result = client.zero_shot_classification(
            text=item_name,
            candidate_labels=valid_categories_names, 
            multi_label=False
        )
        
        best_label = None
        best_score = 0.0

        if hasattr(result, "labels") and hasattr(result, "scores"):
            best_label = result.labels[0]
            best_score = result.scores[0]
        elif isinstance(result, dict) and "labels" in result and "scores" in result:
            best_label = result["labels"][0]
            best_score = result["scores"][0]
        elif isinstance(result, list) and len(result) > 0:
             first = result[0]
             if hasattr(first, "label") and hasattr(first, "score"):
                 best_label = first.label
                 best_score = first.score
             elif isinstance(first, dict):
                 best_label = first.get("label")
                 best_score = first.get("score")

        if best_label:
            sys.stderr.write(f"DEBUG: KI Ergebnis: '{best_label}' ({best_score:.2f})\n")
            # Schwellenwert auf 0.3 angepasst
            if best_score > 0.3:
                return best_label
        
        sys.stderr.write(f"DEBUG: Kein eindeutiges Ergebnis (Score zu niedrig oder falsches Format): {result}\n")
        return None

    except Exception as e:
        sys.stderr.write(f"!!! KI CRASH (HuggingFace Hub): {e}\n")
        return None

def get_category_id_for_item(sb, name):
    if not name: return None
    name_clean = name.lower().strip()

    # 1. Cache prüfen
    try:
        res = sb.table("categorization_cache").select("category_id").eq("keyword", name_clean).execute()
        if res.data and res.data[0]['category_id']:
            sys.stderr.write(f"DEBUG: Cache Treffer für '{name_clean}' -> {res.data[0]['category_id']}\n")
            return res.data[0]['category_id']
    except Exception: pass

    all_categories = get_db_categories(sb)
    if not all_categories: return None 

    # 2. Exakter Keyword-Match (fängt das Offensichtliche ab)
    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            sys.stderr.write(f"DEBUG: Keyword Treffer für '{name_clean}' -> {cat['name']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                }).execute()
            except: pass
            return cat["id"]

    # 3. KI Anfrage VORBEREITEN: Nur reine Namen verwenden (ohne Keywords)
    # Wir bauen eine Map: "Kategoriename" -> "Original Kategorie Objekt"
    label_map = {cat['name']: cat for cat in all_categories}
    candidate_labels = list(label_map.keys())

    # 4. KI Fragen (mit den sauberen Namen)
    found_category_name = get_ai_category_name(candidate_labels, name)

    if found_category_name:
        # 5. Rückauflösung: ID über den Namen finden
        matched_cat = label_map.get(found_category_name)
        
        if matched_cat:
            sys.stderr.write(f"DEBUG: KI Mapping '{found_category_name}' -> ID {matched_cat['id']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, 
                    "category": matched_cat["name"], 
                    "category_id": matched_cat["id"]
                }).execute()
            except: pass
            return matched_cat["id"]

    # Fallback: Sonstiges
    for cat in all_categories:
        if cat["name"].lower() == "sonstiges":
            return cat["id"]

    return None