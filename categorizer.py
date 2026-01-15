import os
import requests
import sys
import time

# Wir nutzen das Zero-Shot Modell via Router
MODEL_ID = "facebook/bart-large-mnli"
HF_API_URL = f"https://router.huggingface.co/models/{MODEL_ID}"
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

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
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    # --- WICHTIGE ÄNDERUNG ---
    # Kein Chat-Prompt mehr! Wir senden das Item und die Liste der Labels.
    # Das Zero-Shot Modell erwartet "candidate_labels" in den Parametern.
    payload = {
        "inputs": item_name,
        "parameters": {
            "candidate_labels": valid_categories_names,
            "multi_label": False
        }
    }
    # -------------------------
    
    # Retry-Loop, falls das Modell noch lädt (Error 503)
    for attempt in range(3):
        try:
            sys.stderr.write(f"DEBUG: Sende Zero-Shot Anfrage für '{item_name}' (Versuch {attempt+1})...\n")
            
            response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=10)
            
            # Fehlerprüfung
            if response.status_code != 200:
                sys.stderr.write(f"!!! API Status {response.status_code}: {response.text}\n")
                # Wenn das Modell lädt, warten wir kurz
                if "loading" in response.text.lower():
                    time.sleep(3)
                    continue
                return None

            result = response.json()

            # Manchmal ist das Ergebnis eine Liste, manchmal ein Dict
            if isinstance(result, list):
                result = result[0]
            
            # Prüfen, ob wir Labels zurückbekommen haben
            if "labels" in result and "scores" in result:
                best_label = result['labels'][0]
                best_score = result['scores'][0]
                
                sys.stderr.write(f"DEBUG: KI Ergebnis: '{best_label}' ({best_score:.2f})\n")
                
                if best_score > 0.2:
                    return best_label
                else:
                    return None
            else:
                sys.stderr.write(f"!!! Unerwartetes Antwortformat: {result}\n")
                return None

        except Exception as e:
            sys.stderr.write(f"!!! KI CRASH: {e}\n")
            return None
        
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