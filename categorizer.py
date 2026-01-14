import os
import requests
from supabase_utils import data, error # Falls du diese Helfer hast, sonst direkt data/error zugriff

# Hugging Face Konfiguration (bleibt gleich)
HF_API_URL = "https://router.huggingface.co/hf-inference/v1/chat/completions"
HF_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")

# Lokales Mapping (bleibt gleich)
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

def get_ai_category_name(name):
    """Liefert NUR den Namen der Kategorie via KI."""
    if not HF_TOKEN:
        return "Sonstiges"
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    prompt = f"Ordne '{name}' zu: {', '.join(VALID_CATEGORIES)}. Nur Kategorie-Name."
    payload = {
        "model": "meta-llama/Llama-3.2-3B-Instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 15, "temperature": 0.1
    }
    
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=5)
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            for cat in VALID_CATEGORIES:
                if cat.lower() in content.lower():
                    return cat
    except Exception as e:
        print(f"KI Fehler: {e}")
    return "Sonstiges"

def get_category_id_by_name(sb, cat_name):
    """Hilfsfunktion: Sucht die ID zu einem Namen in der globalen Tabelle."""
    try:
        res = sb.table("resource_categories").select("id").eq("name", cat_name).limit(1).execute()
        if res.data:
            return res.data[0]['id']
    except Exception:
        pass
    return None

def get_category_id_for_item(sb, name):
    """
    Hauptfunktion: Gibt direkt die ID zurück (oder None).
    Ablauf: Cache (ID) -> Keywords (Name->ID) -> KI (Name->ID) -> Cache Update
    """
    if not name: return None
    name_clean = name.lower().strip()

    # 1. Cache Check (Hat jetzt direkt die ID!)
    try:
        res = sb.table("categorization_cache").select("category_id").eq("keyword", name_clean).execute()
        if res.data and res.data[0]['category_id']:
            return res.data[0]['category_id']
    except Exception:
        pass

    # 2. Name ermitteln (Lokal oder KI)
    found_name = None
    for category, keywords in KEYWORD_MAPPING.items():
        if any(kw in name_clean for kw in keywords):
            found_name = category
            break
    
    if not found_name:
        found_name = get_ai_category_name(name)

    # 3. ID zum Namen suchen (Datenbank-Lookup)
    found_id = get_category_id_by_name(sb, found_name)

    # 4. Im Cache speichern (Jetzt mit ID!)
    if found_id:
        try:
            sb.table("categorization_cache").upsert({
                "keyword": name_clean,
                "category": found_name,   # Wir speichern den Namen zur Info trotzdem
                "category_id": found_id   # Das Wichtige für die Verknüpfung
            }).execute()
        except Exception:
            pass

    return found_id