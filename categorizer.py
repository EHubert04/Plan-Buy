import os
import requests
import json

# Wir nutzen die neue Router-API (OpenAI-kompatibel)
# Modell: Ein leichtes, schnelles Modell (kostenlos im Free Tier)
HF_API_URL = "https://router.huggingface.co/hf-inference/v1/chat/completions"
HF_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")

KEYWORD_MAPPING = {
    "Obst & Gemüse": ["apfel", "banane", "birne", "tomate", "gurke", "salat", "zwiebel", "kartoffel", "paprika", "zitrone"],
    "Milchprodukte": ["milch", "käse", "quark", "joghurt", "butter", "sahne", "kaese"],
    "Getränke": ["wasser", "saft", "bier", "wein", "cola", "limo", "kaffee", "tee", "sprudel"],
    "Backwaren": ["brot", "brötchen", "baguette", "toast", "croissant", "broetchen"],
    "Fleisch & Fisch": ["hähnchen", "hackfleisch", "lachs", "wurst", "fleisch", "schinken", "haehnchen"],
    "Vorrat": ["nudeln", "reis", "mehl", "zucker", "salz", "öl", "konserve", "oel"],
    "Hygiene": ["seife", "shampoo", "zahnpasta", "klopapier", "duschgel", "wc"]
}

VALID_CATEGORIES = list(KEYWORD_MAPPING.keys()) + ["Sonstiges"]

def get_ai_category(name):
    """Fragt die neue Hugging Face Router API."""
    if not HF_TOKEN:
        print("Kein Hugging Face Token gefunden.")
        return "Sonstiges"
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    # Wir bauen einen Prompt für ein Chat-Modell
    prompt = f"Ordne das Produkt '{name}' einer dieser Kategorien zu: {', '.join(VALID_CATEGORIES)}. Antworte NUR mit dem Namen der Kategorie, ohne Satzzeichen."

    payload = {
        "model": "meta-llama/Llama-3.2-3B-Instruct", # Kleines, schnelles Modell
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 15,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=8)
        
        if response.status_code == 200:
            result = response.json()
            # Antwort extrahieren
            content = result['choices'][0]['message']['content'].strip()
            # Bereinigen (falls Punkte oder Anführungszeichen dabei sind)
            for cat in VALID_CATEGORIES:
                if cat.lower() in content.lower():
                    return cat
        else:
            print(f"KI API Fehler: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"KI Verbindungsfehler: {e}")
    
    return "Sonstiges" # Fallback, damit die App nicht abstürzt

def get_category_for_item(sb, name):
    if not name: return "Sonstiges"
    name_clean = name.lower().strip()

    # 1. DB Cache
    try:
        res = sb.table("categorization_cache").select("category").eq("keyword", name_clean).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['category']
    except Exception:
        pass

    # 2. Keywords
    for category, keywords in KEYWORD_MAPPING.items():
        if any(kw in name_clean for kw in keywords):
            return category

    # 3. KI (Neue API)
    found_category = get_ai_category(name)

    # 4. Speichern
    if found_category and found_category != "Sonstiges":
        try:
            sb.table("categorization_cache").upsert({"keyword": name_clean, "category": found_category}).execute()
        except Exception:
            pass

    return found_category