import os
import requests

# Hugging Face Konfiguration
HF_API_URL = "https://router.huggingface.co/hf-inference/v1/chat/completions"
HF_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")

def get_db_categories(sb):
    """
    Lädt alle Kategorien und Keywords frisch aus der Datenbank.
    Erwartet, dass die Spalte 'keywords' in der DB kommagetrennte Wörter enthält.
    """
    try:
        # Wir holen ID, Name und Keywords
        res = sb.table("resource_categories").select("id, name, keywords").execute()
        rows = getattr(res, "data", []) or []
        
        parsed_rows = []
        for r in rows:
            # Keywords String "Apfel, Banane" -> Liste ["apfel", "banane"]
            raw_kw = r.get("keywords") or ""
            # Falls keywords null ist, leere Liste nehmen
            if not raw_kw:
                kw_list = []
            else:
                kw_list = [k.strip().lower() for k in raw_kw.split(",") if k.strip()]
            
            parsed_rows.append({
                "id": r["id"],
                "name": r["name"],
                "keywords": kw_list
            })
        return parsed_rows
    except Exception as e:
        print(f"Fehler beim Laden der Kategorien: {e}")
        return []

def get_ai_category_name(valid_categories_names, item_name):
    """Fragt die KI und gibt ihr nur die aktuell in der DB existierenden Kategorien zur Auswahl."""
    if not HF_TOKEN or not valid_categories_names:
        return None
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    
    # Prompt baut sich dynamisch aus den DB-Kategorien auf
    cats_str = ", ".join(valid_categories_names)
    prompt = f"Ordne das Produkt '{item_name}' einer dieser Kategorien zu: {cats_str}. Antworte NUR mit dem exakten Namen der Kategorie."
    
    payload = {
        "model": "meta-llama/Llama-3.2-3B-Instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 20, "temperature": 0.1
    }
    
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=6)
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            # Wir prüfen, ob die KI-Antwort zu einer unserer Kategorien passt
            for cat_name in valid_categories_names:
                if cat_name.lower() in content.lower():
                    return cat_name
    except Exception as e:
        print(f"KI Fehler: {e}")
        
    return None

def get_category_id_for_item(sb, name):
    """
    Hauptfunktion:
    1. Cache (exakter Treffer) -> liefert sofort ID
    2. DB-Keywords (Keyword-Suche in der Tabelle resource_categories) -> liefert ID
    3. KI (mit dynamischer Liste aus DB) -> liefert Name -> wir suchen ID
    """
    if not name: return None
    name_clean = name.lower().strip()

    # 1. Cache Check (Schnellster Weg)
    try:
        res = sb.table("categorization_cache").select("category_id").eq("keyword", name_clean).execute()
        if res.data and res.data[0]['category_id']:
            return res.data[0]['category_id']
    except Exception:
        pass

    # -- Ab hier brauchen wir die globale Liste aus der DB --
    all_categories = get_db_categories(sb)
    if not all_categories:
        # Fallback: Wenn DB leer ist oder Fehler, abbrechen
        return None 

    # 2. Suche in den Keywords der Datenbank
    # Wir iterieren durch die geladenen Kategorien
    for cat in all_categories:
        if any(kw in name_clean for kw in cat["keywords"]):
            # Treffer! Wir haben die ID.
            
            # (Optional: Cache updaten, damit es nächstes Mal noch schneller geht)
            try:
                sb.table("categorization_cache").upsert({
                    "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                }).execute()
            except: pass
            
            return cat["id"]

    # 3. KI fragen (mit den Namen aus der DB als Auswahl)
    valid_names = [c["name"] for c in all_categories]
    found_name = get_ai_category_name(valid_names, name)

    if found_name:
        # Wir müssen den Namen zurück in eine ID wandeln
        for cat in all_categories:
            if cat["name"].lower() == found_name.lower():
                # Gefunden! Speichern und zurückgeben
                try:
                    sb.table("categorization_cache").upsert({
                        "keyword": name_clean, "category": cat["name"], "category_id": cat["id"]
                    }).execute()
                except: pass
                return cat["id"]

    # Fallback: Versuchen, "Sonstiges" zu finden (falls vorhanden)
    for cat in all_categories:
        if cat["name"].lower() == "sonstiges":
            return cat["id"]

    return None