import os
import sys
import google.generativeai as genai

# Konfiguration des Clients (Ähnlich wie create_client bei Supabase)
# Das SDK kümmert sich automatisch um URLs und Versionierung
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def configure_genai():
    """Initialisiert den Google Client, falls ein Key vorhanden ist."""
    if not GEMINI_API_KEY:
        return False
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return True
    except Exception as e:
        sys.stderr.write(f"!!! GEMINI CONFIG ERROR: {e}\n")
        return False

def get_db_categories(sb):
    """Liest Kategorien aus der Supabase DB (unverändert)."""
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
    """Nutzt das Google SDK für die Anfrage."""
    if not configure_genai():
        sys.stderr.write("DEBUG: KI übersprungen (Kein GEMINI_API_KEY)\n")
        return None
    
    cats_str = ", ".join(valid_categories_names)
    prompt = f"Ordne das Produkt '{item_name}' einer dieser Kategorien zu: {cats_str}. Antworte NUR mit dem exakten Namen der Kategorie, ohne Satzzeichen."
    
    try:
        sys.stderr.write(f"DEBUG: Frage Gemini SDK nach '{item_name}'...\n")
        
        # Modell-Instanziierung (wie sb.table(...))
        # Wir nutzen 'gemini-1.5-flash', da es schnell und effizient ist.
        # Fallback auf 'gemini-pro' möglich, falls Flash in der Region nicht verfügbar ist.
        model = genai.GenerativeModel('gemini-pro')
        
        # Der eigentliche Aufruf (wie .execute())
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=20
            )
        )
        
        # Antwort verarbeiten
        if response.text:
            content = response.text.strip()
            sys.stderr.write(f"DEBUG: KI Antwort: '{content}'\n")

            for cat_name in valid_categories_names:
                if cat_name.lower() in content.lower():
                    return cat_name
        else:
            sys.stderr.write("DEBUG: Leere Antwort von KI\n")

    except Exception as e:
        sys.stderr.write(f"!!! KI SDK FEHLER: {e}\n")
        
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

    # 3. KI fragen (via SDK)
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