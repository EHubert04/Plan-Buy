from flask import Flask, jsonify, request


app = Flask(__name__)


# Temporärer Speicher (später eine Datenbank wie SQLite)
data = {
    "tasks": ["Projekt planen", "Code schreiben"],
    "resources": ["Laptop", "Kaffee"]
}

@app.route('/get_data', methods=['GET'])
def get_data():
    return jsonify(data)

@app.route('/add_item', methods=['POST'])
def add_item():
    item = request.json.get('item')
    category = request.json.get('category') # 'tasks' oder 'resources'
    if category in data:
        data[category].append(item)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)