from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# In-Memory Speicher (wird bei Neustart gelöscht)
projects = [
    {
        "id": 1, 
        "name": "Mein erstes Projekt", 
        "todos": ["Beispiel-Aufgabe"], 
        "resources": [{name:"Beispiel-Einkauf", "quantity": 1}]
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
            quantity = data.get('quantity', 1)  # default 1, falls nicht übergeben
            project['resources'].append({
                "name": data['content'],
                "quantity": quantity})
        return jsonify(project)

if __name__ == '__main__':
    app.run(debug=True)