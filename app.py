from flask import Flask, render_template
from flask_cors import CORS
import os

from materie.matematica import matematica_bp
from materie.arte import arte_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(matematica_bp)
app.register_blueprint(arte_bp)


@app.route("/")
def landing():
    return render_template("landing.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
