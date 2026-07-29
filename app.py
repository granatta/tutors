from flask import Flask, render_template
from flask_cors import CORS
import os

from materie.matematica import matematica_bp
from materie.arte import arte_bp
from materie.grammatica import grammatica_bp
from materie.inglese import inglese_bp
from materie.tedesco import tedesco_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(matematica_bp)
app.register_blueprint(arte_bp)
app.register_blueprint(grammatica_bp)
app.register_blueprint(inglese_bp)
app.register_blueprint(tedesco_bp)


@app.route("/")
def landing():
    return render_template("landing.html")

@app.route('/coming-soon')
def coming_soon():
    return render_template('coming_soon.html')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
