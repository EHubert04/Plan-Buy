import os
import requests
import json

# Hugging Face Konfiguration
HF_API_URL = "https://router.huggingface.co/hf-inference/v1/chat/completions"
HF_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")

KEYWORD_MAPPING = {
    "Obst & Gemüse": ["apfel", "banane", "birne", "tomate", "gurke", "salat", "zwiebel", "kartoffel", "paprika", "zitrone"],
    "Milchprodukte": ["milch", "käse", "quark", "joghurt", "butter", "sahne", "kaese"],
    "Getränke": ["wasser", "saft", "bier", "wein", "cola", "limo", "kaffee", "tee", "sprudel"],
    "Backwaren": ["brot", "brötchen", "baguette", "toast", "croissant", "broetchen", "keks", "gebäck"],
    "Fleisch & Fisch": ["hähnchen", "hackfleisch", "lachs", "wurst", "fleisch", "schinken", "haehnchen"],
    "Vorrat": ["nudeln", "reis", "mehl", "zucker", "salz", "öl", "konserve", "oel"],
    "Hygiene": ["seife", "shampoo", "zahnpasta", "klopapier", "duschgel", "wc"],
    "Werkzeug": ["hammer", "zange", "schraube", "bohrer", "nagel"],
    "Baustoffe": ["zement", "holz", "stein", "farbe", "lack"]
}

VALID_CATEGORIES = list(KEYWORD_MAPPING.keys()) + ["Sonstiges"]

def get_ai_category(name):
    """Fragt die KI nach einer Kategorie."""
    if not HF_TOKEN:
        print("Kein Hugging Face Token.")
        return "Sonstiges"
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    prompt = f"Ordne das Produkt '{name}' einer dieser Kategorien zu: {', '.join(VALID_CATEGORIES)}. Antworte NUR mit dem Namen der Kategorie."

    payload = {
        "model": "meta-llama/Llama-3.2-3B-Instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 15,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=5)
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            for cat in VALID_CATEGORIES:
                if cat.lower() in content.lower():
                    return cat
        else:
            print(f"KI Fehler: {response.status_code}")
    except Exception as e:
        print(f"KI Exception: {e}")
    
    return "Sonstiges"

def get_category_for_item(sb, name):
    if not name: return "Sonstiges"
    name_clean = name.lower().strip()
    
    found_category = None

    # 1. Zuerst im Cache schauen (DB)
    try:
        res = sb.table("categorization_cache").select("category").eq("keyword", name_clean).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['category'] # Wenn schon in DB, fertig.
    except Exception:
        pass

    # 2. Wenn nicht in DB -> In lokaler Liste suchen
    if not found_category:
        for category, keywords in KEYWORD_MAPPING.items():
            if any(kw in name_clean for kw in keywords):
                found_category = category
                break # Gefunden! Aber wir returnen noch nicht, damit wir speichern können.

    # 3. Wenn immer noch nicht gefunden -> KI fragen
    if not found_category:
        found_category = get_ai_category(name)

    # 4. Ergebnis IMMER in den Cache speichern (Lerneffekt)
    if found_category and found_category != "Sonstiges":
        try:
            sb.table("categorization_cache").upsert({
                "keyword": name_clean, 
                "category": found_category
            }).execute()
            print(f"Gelernt: {name_clean} -> {found_category}")
        except Exception as e:
            print(f"Fehler beim Cache-Speichern: {e}")

    return found_category if found_category else "Sonstiges"