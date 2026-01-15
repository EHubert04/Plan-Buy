import os
import requests
import sys
import time

# Token laden
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

# Wir nutzen das Zero-Shot Modell via neuer Router-URL
MODEL_ID = "facebook/bart-large-mnli"
API_URL = f"https://router.huggingface.co/models/{MODEL_ID}"

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

def query_huggingface(payload, retries=3):
    """Hilfsfunktion für den Request mit Retry-Logik bei 'Model Loading'"""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    for i in range(retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=10)
            data = response.json()
            
            # Fall 1: Modell lädt noch -> Warten und nochmal versuchen
            if isinstance(data, dict) and "error" in data and "loading" in data.get("error", "").lower():
                wait_time = data.get("estimated_time", 5)
                sys.stderr.write(f"DEBUG: Modell lädt noch... warte {wait_time:.1f}s (Versuch {i+1}/{retries})\n")
                time.sleep(wait_time)
                continue # Nächster Schleifendurchlauf
            
            return data
            
        except Exception as e:
            sys.stderr.write(f"!!! API Request Fehler: {e}\n")
            
    return None

def get_ai_category_name(valid_categories_names, item_name):
    if not HF_TOKEN:
        sys.stderr.write("DEBUG: KI übersprungen (Kein HF_TOKEN)\n")
        return None
    
    # Payload für Zero-Shot Classification
    payload = {
        "inputs": item_name,
        "parameters": {"candidate_labels": valid_categories_names}
    }
    
    try:
        sys.stderr.write(f"DEBUG: Starte Zero-Shot für '{item_name}'...\n")
        
        result = query_huggingface(payload)
        
        # Sicherstellen, dass wir Daten haben
        if not result:
            return None

        # Falls die API eine Liste zurückgibt (manchmal bei Router der Fall)
        if isinstance(result, list):
            result = result[0]

        # Fehler-Check: Haben wir überhaupt Labels bekommen?
        if "labels" not in result or "scores" not in result:
            sys.stderr.write(f"!!! KI Fehler: Unerwartete Antwort: {result}\n")
            return None

        # Auslesen
        best_label = result['labels'][0]
        best_score = result['scores'][0]
        
        sys.stderr.write(f"DEBUG: KI Ergebnis: '{best_label}' ({best_score:.2f})\n")
        
        if best_score > 0.2:
            return best_label
        
    except Exception as e:
        sys.stderr.write(f"!!! KI CRASH: {e}\n")
        
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