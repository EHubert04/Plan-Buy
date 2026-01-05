from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Wir nutzen eine einfache Liste als "Datenbank-Ersatz"
# Jeder Eintrag ist ein Dictionary: {"content": "Text", "category": "task"}
data_storage = []

# Routen
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_data', methods=['GET'])
def get_data():
    # Wir filtern die Liste manuell nach Kategorien
    tasks = [item['content'] for item in data_storage if item['category'] == 'task']
    resources = [item['content'] for item in data_storage if item['category'] == 'resource']
    
    return jsonify({
        "tasks": tasks,
        "resources": resources
    })

@app.route('/add_item', methods=['POST'])
def add_item():
    data = request.json
    
    # Neuen Eintrag direkt in die Liste speichern
    new_entry = {
        "content": data['item'],
        "category": data['category']
    }
    data_storage.append(new_entry)
    
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)