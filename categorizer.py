import os
import requests
import sys

# Wir nutzen Phi-3.5, da dein Code einen Chat-Prompt sendet
MODEL_ID = "microsoft/Phi-3.5-mini-instruct"

# WICHTIG: Die neue URL mit "router" UND "hf-inference"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_ID}"

# Token laden (probiert beide gängigen Variablennamen)
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

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
        sys.stderr.write("DEBUG: KI übersprungen (Kein Token)\n")
        return None
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    cats_str = ", ".join(valid_categories_names)
    
    # Prompt Formatierung für Phi-3 (Chat-Stil)
    formatted_prompt = f"<|user|>\nOrdne das Produkt '{item_name}' einer dieser Kategorien zu: {cats_str}. Antworte NUR mit dem exakten Namen der Kategorie.<|end|>\n<|assistant|>"
    
    # Payload für Text-Generation Modelle
    payload = {
        "inputs": formatted_prompt,
        "parameters": {
            "max_new_tokens": 50,
            "return_full_text": False,
            "temperature": 0.1
        }
    }
    
    try:
        sys.stderr.write(f"DEBUG: Frage KI (Phi-3.5) nach '{item_name}'...\n")
        
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            sys.stderr.write(f"!!! KI API FEHLER: {response.status_code} - {response.text}\n")
            return None

        # Die Router-API gibt oft eine Liste zurück: [{'generated_text': 'Obst'}]
        result = response.json()
        content = ""
        
        if isinstance(result, list) and len(result) > 0:
            content = result[0].get('generated_text', '').strip()
        elif isinstance(result, dict) and 'generated_text' in result:
             content = result.get('generated_text', '').strip()

        sys.stderr.write(f"DEBUG: KI Antwort für '{item_name}': '{content}'\n")

        # Abgleich der Antwort mit den gültigen Kategorien
        for cat_name in valid_categories_names:
            if cat_name.lower() in content.lower():
                return cat_name
                
    except Exception as e:
        sys.stderr.write(f"!!! KI CRASH: {e}\n")
        
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

    # 2. Exakte Keywords prüfen
    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            sys.stderr.write(f"DEBUG: Keyword Treffer für '{name_clean}' -> {cat['name']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                }).execute()
            except: pass
            return cat["id"]

    # 3. KI fragen
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

    # 4. Fallback: Sonstiges
    for cat in all_categories:
        if cat["name"].lower() == "sonstiges":
            return cat["id"]

    return None