from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("base.html")


@app.route("/planning")
def planning():
    plans = [
        {"id": 1, "name": "Hausbau – Fundament"},
        {"id": 2, "name": "Wochenessen"}
    ]
    return render_template("planning.html", plans=plans)


@app.route("/shopping")
def shopping():
    items = [
        {"name": "Zement 25kg", "category": "Baumarkt > Beton"},
        {"name": "Milch", "category": "Supermarkt > Milchprodukte"}
    ]
    return render_template("shopping.html", items=items)


@app.route("/planning/<int:plan_id>/add-to-shopping", methods=["POST"])
def add_to_shopping(plan_id):
    # später: Materialien → Einkaufseinträge
    print(f"Plan {plan_id} zur Einkaufsliste hinzugefügt")
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
