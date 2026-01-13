# categorizer.py

# Lokales Mapping für Schlagwörter (Fallback)
KEYWORD_MAPPING = {
    "Obst & Gemüse": ["apfel", "banane", "birne", "tomate", "gurke", "salat", "zwiebel", "kartoffel", "paprika", "zitrone"],
    "Milchprodukte": ["milch", "käse", "quark", "joghurt", "butter", "sahne", "kaese"],
    "Getränke": ["wasser", "saft", "bier", "wein", "cola", "limo", "kaffee", "tee", "sprudel"],
    "Backwaren": ["brot", "brötchen", "baguette", "toast", "croissant", "broetchen"],
    "Fleisch & Fisch": ["hähnchen", "hackfleisch", "lachs", "wurst", "fleisch", "schinken", "haehnchen"],
    "Vorrat": ["nudeln", "reis", "mehl", "zucker", "salz", "öl", "konserve", "oel"],
    "Hygiene": ["seife", "shampoo", "zahnpasta", "klopapier", "duschgel", "wc"]
}

def get_category_for_item(sb, name):
    """
    Kategorisiert einen Artikel ohne KI.
    Reihenfolge: 1. DB-Cache (exakt), 2. Lokale Keywords, 3. Sonstiges
    """
    if not name:
        return "Sonstiges"
    
    name_clean = name.lower().strip()

    # 1. Schritt: In der Datenbank nach einem exakten Treffer suchen
    try:
        # Wir nutzen die Tabelle 'categorization_cache'
        res = sb.table("categorization_cache").select("category").eq("keyword", name_clean).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['category']
    except Exception as e:
        print(f"Datenbank-Fehler beim Cache-Read: {e}")

    # 2. Schritt: Schlagwort-Suche in der lokalen Liste
    found_category = "Sonstiges"
    for category, keywords in KEYWORD_MAPPING.items():
        if any(kw in name_clean for kw in keywords):
            found_category = category
            break

    # 3. Schritt: Treffer in der DB speichern (Lerneffekt), falls es nicht "Sonstiges" ist
    if found_category != "Sonstiges":
        try:
            # Speichere für das nächste Mal in der DB
            sb.table("categorization_cache").upsert({"keyword": name_clean, "category": found_category}).execute()
        except Exception:
            pass # Falls es schon existiert oder DB-Fehler

    return found_category