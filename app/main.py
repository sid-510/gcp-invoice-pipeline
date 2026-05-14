"""
Invoice Automation Pipeline — Flask entry point.

Minimal scaffold with a health endpoint. Business logic (Document AI
integration, BigQuery writes, GSTIN validation) lives in dedicated
modules that will be added in subsequent commits.
"""

import logging
import os

from flask import Flask, jsonify


def create_app() -> Flask:
    """Application factory. Configures logging and registers routes."""
    app = Flask(__name__)

    # Basic logging configuration.
    # Cloud Run captures stdout/stderr automatically, so we don't
    # configure file handlers or external sinks here.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @app.get("/health")
    def health():
        """Liveness/readiness endpoint for Cloud Run."""
        return jsonify({"status": "ok"}), 200

    @app.get("/")
    def index():
        """Placeholder index. Real upload UI will replace this later."""
        return jsonify({
            "service": "invoice-pipeline",
            "version": "0.1.0",
            "status": "scaffold",
        }), 200

    return app


# Module-level app instance, used by Gunicorn in production.
# When Gunicorn runs `gunicorn main:app`, it imports this module
# and looks for the `app` symbol.
app = create_app()


if __name__ == "__main__":
    # Local development entry point.
    # In production, Gunicorn imports `app` directly and ignores this block.
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)