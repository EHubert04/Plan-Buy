# categorizer.py
from sentence_transformers import SentenceTransformer, util
import torch


model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

CATEGORIES = [
    "Obst & Gemüse", 
    "Milchprodukte", 
    "Getränke", 
    "Backwaren", 
    "Fleisch & Fisch", 
    "Vorrat", 
    "Hygiene", 
    "Sonstiges"
]

# Vorberechnen der Embeddings für die Kategorien (spart Zeit bei jeder Anfrage)
CATEGORY_EMBEDDINGS = model.encode(CATEGORIES, convert_to_tensor=True)

def get_category_for_item(sb, name):
    """
    Prüft erst den DB-Cache und nutzt bei Miss den Sentence Transformer.
    """
    if not name:
        return "Sonstiges"
    
    name_clean = name.lower().strip()

    # 1. DB-Cache prüfen (exakter Treffer)
    try:
        res = sb.table("categorization_cache").select("category").eq("keyword", name_clean).execute()
        if res.data:
            return res.data[0]['category']
    except Exception as e:
        print(f"Cache-Fehler: {e}")

    # 2. KI nutzen (Sentence Transformer Fallback)
    category = _predict_with_transformers(name_clean)

    # 3. Ergebnis im Cache speichern für das nächste Mal
    try:
        sb.table("categorization_cache").insert({
            "keyword": name_clean, 
            "category": category
        }).execute()
    except Exception:
        pass 

    return category

def _predict_with_transformers(item_name):
    """Berechnet die Ähnlichkeit des Artikels zu allen Kategorien."""
    # Embedding für den eingegebenen Artikel erstellen
    item_embedding = model.encode(item_name, convert_to_tensor=True)
    
    # Kosinus-Ähnlichkeit zu allen Kategorie-Embeddings berechnen
    cosine_scores = util.cos_sim(item_embedding, CATEGORY_EMBEDDINGS)[0]
    
    # Den Index mit der höchsten Ähnlichkeit finden
    best_idx = torch.argmax(cosine_scores).item()
    
    # Optional: Ein Schwellenwert (z.B. 0.35). Wenn die Ähnlichkeit zu gering ist -> Sonstiges
    if cosine_scores[best_idx] < 0.35:
        return "Sonstiges"
        
    return CATEGORIES[best_idx]
