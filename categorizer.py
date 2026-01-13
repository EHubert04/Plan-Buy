from sentence_transformers import SentenceTransformer
import numpy as np


model = SentenceTransformer("all-MiniLM-L6-v2")
supabase.table("ressource_categories").update({
    "embedding": embed_category(cat)
}).eq("id", cat["id"]).execute()

def keyword_match(name, categories):
    name = name.lower().strip()

    for cat in categories:
        examples = [k.strip().lower() for k in cat["keywords"].split(",")]
        if name in examples:
            return cat["name"]

    return None

def embed_category(category):
    text = f"{category['name']} {category['keywords']}"
    emb = model.encode(text)
    return emb.tolist()

def load_categories():
    return supabase.table("ressource_categories").select("*").execute().data
def get_category_for_item(name, categories):
    
    name = name.lower()

    for cat in categories:
        keywords = cat["keywords"].lower().split(",")
        if any(k.strip() in name for k in keywords):
            return cat["name"]
    return "Sonstiges"
def cosine(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def classify_item(name):
    item_emb = model.encode(name)

    categories = supabase.table("resource_categories") \
        .select("name, embedding") \
        .execute().data

    best = None
    score = -1

    for cat in categories:
        sim = cosine(item_emb, cat["embedding"])
        if sim > score:
            best = cat["name"]
            score = sim
        elif similarity < 0.55:
            return "Sonstige"
    return best
