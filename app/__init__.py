# app/__init__.py

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

# Create the Flask application
app = Flask(__name__)

# Optional: Reverse proxy support (important for nginx + subpath deployment)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Optional: Set base path (not strictly necessary unless you're using url_for with SCRIPT_NAME)
app.config['APPLICATION_ROOT'] = '/github-pr-viewer'

# Import routes after creating the app (avoids circular imports)
from . import routes

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
