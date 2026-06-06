"""
Minimal server — starts the background scheduler and exposes a health check.
"""

import logging
from flask import Flask
from config import FLASK_SECRET_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

from scheduler import start_scheduler
_scheduler = start_scheduler()


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
