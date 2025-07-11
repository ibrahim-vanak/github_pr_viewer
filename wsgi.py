from app import app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix

# Ensure the app handles reverse proxy headers properly
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Serve the Flask app under a subpath (/github-pr-viewer)
application = DispatcherMiddleware(None, {
    '/github-pr-viewer': app
})

