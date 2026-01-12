# categorizer.py

def get_category_for_item(name):
    """
    Weist einem Artikelnamen basierend auf Schlagwörtern eine Kategorie zu.
    """
    if not name:
        return "Sonstiges"
        
    name = name.lower()
    
    # Mapping von Kategorien zu Schlagwörtern
    mapping = {
        "Obst & Gemüse": ["apfel", "banane", "birne", "trauben", "zitrone", "tomate", "gurke", "salat", "zwiebel", "kartoffel"],
        "Milchprodukte": ["milch", "käse", "quark", "joghurt", "butter", "sahne"],
        "Getränke": ["wasser", "saft", "bier", "wein", "cola", "limo", "kaffee", "tee"],
        "Backwaren": ["brot", "brötchen", "baguette", "toast", "croissant"],
        "Fleisch & Fisch": ["hähnchen", "hackfleisch", "lachs", "wurst", "fleisch", "schinken"],
        "Vorrat": ["nudeln", "reis", "mehl", "zucker", "salz", "öl", "konserve"],
        "Hygiene": ["seife", "shampoo", "zahnpasta", "klopapier", "duschgel"]
    }
    
    for category, keywords in mapping.items():
        if any(keyword in name for keyword in keywords):
            return category
            
    return "Sonstiges"