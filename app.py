from flask import Flask, render_template, request, jsonify
import os
import psycopg2

app = Flask(__name__)

# In-Memory Speicher (wird bei Neustart gelöscht)
projects = [
    {
        "id": 1, 
        "name": "Mein erstes Projekt", 
        "todos": ["Beispiel-Aufgabe"], 
        "resources": [{"name":"Beispiel-Einkauf", "quantity": 1}]
    }
]

@app.route('/')
def index():
    return render_template('index.html')

# Alle Projekte abrufen
@app.route('/api/projects', methods=['GET'])
def get_projects():
    return jsonify(projects)

# Neues Projekt erstellen
@app.route('/api/projects', methods=['POST'])
def add_project():
    data = request.json
    new_id = len(projects) + 1
    new_project = {
        "id": new_id,
        "name": data['name'],
        "todos": [],
        "resources": []
    }
    projects.append(new_project)
    return jsonify(new_project)

# Item (Todo oder Ressource) zu Projekt hinzufügen
@app.route('/api/projects/<int:p_id>/items', methods=['POST'])
def add_item(p_id):
    data = request.json
    project = next((p for p in projects if p['id'] == p_id), None)
    if project:
        if data['type'] == 'todo':
            project['todos'].append(data['content'])
        else:
            quantity = data.get('quantity', 1) 
            project['resources'].append({
                "name": data['content'],
                "quantity": quantity})
        return jsonify(project)
    
@app.get("/health/app")
def health_app():
    return {"ok": True}, 200

@app.get("/health/db")
def health_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"ok": False, "error": "DATABASE_URL is not set"}, 500

    # Manche Setups nutzen "postgres://"
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        conn = psycopg2.connect(db_url, connect_timeout=30)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        cur.close()
        conn.close()
        return {"ok": True, "db": "reachable"}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True)