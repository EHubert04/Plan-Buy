from flask import Flask, render_template
import os
from api_routes import api_bp

app = Flask(__name__)
app.register_blueprint(api_bp)


@app.route("/")
def index():
    return render_template(
        "index.html",
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
    )


if __name__ == "__main__":
    app.run(debug=True)
