import os
import requests
import sys
import json

# Wir nutzen Gemini 1.5 Flash Latest auf der v1beta API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# WICHTIG: "gemini-1.5-flash-latest" ist oft robuster als der Kurzname
# Wir nutzen wieder v1beta, da neuere Modelle dort zuverlässiger sind
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

def get_db_categories(sb):
    """Liest Kategorien aus der Supabase DB."""
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
    """Fragt Google Gemini nach der Kategorie."""
    if not GEMINI_API_KEY:
        sys.stderr.write("DEBUG: KI übersprungen (Kein GEMINI_API_KEY gesetzt)\n")
        return None
    
    cats_str = ", ".join(valid_categories_names)
    
    # Prompt
    prompt = f"Ordne das Produkt '{item_name}' einer dieser Kategorien zu: {cats_str}. Antworte NUR mit dem exakten Namen der Kategorie, ohne Satzzeichen oder Erklärung."
    
    # Payload für Gemini API
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 20
        }
    }
    
    headers = {'Content-Type': 'application/json'}

    try:
        sys.stderr.write(f"DEBUG: Frage Gemini (v1beta/latest) nach '{item_name}'...\n")
        
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            sys.stderr.write(f"!!! KI API FEHLER: {response.status_code} - {response.text}\n")
            return None

        # Antwort parsen
        data = response.json()
        try:
            content = data['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError):
            sys.stderr.write(f"!!! KI Antwort Format unerwartet: {data}\n")
            return None

        sys.stderr.write(f"DEBUG: KI Antwort für '{item_name}': '{content}'\n")

        # Validierung: Ist die Antwort eine bekannte Kategorie?
        for cat_name in valid_categories_names:
            if cat_name.lower() in content.lower():
                return cat_name
                
    except Exception as e:
        sys.stderr.write(f"!!! KI CRASH: {e}\n")
        
    return None

def get_category_id_for_item(sb, name):
    """Hauptlogik: Cache -> Keywords -> KI -> Fallback"""
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

    # 2. Exakte Keywords prüfen (lokal, schnell)
    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            sys.stderr.write(f"DEBUG: Keyword Treffer für '{name_clean}' -> {cat['name']}\n")
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                }).execute()
            except: pass
            return cat["id"]

    # 3. KI fragen (Google Gemini)
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