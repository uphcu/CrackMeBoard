import json
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv("REDIS_URL", "memory://"),
)


def create_app():
    app = Flask(__name__)

    # Config
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(basedir), 'instance', 'crackmeboard.db')}",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_TIME_LIMIT"] = 3600  # 1 hour
    app.config["TOTP_ISSUER"] = os.getenv("TOTP_ISSUER", "CrackMeBoard")

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "로그인이 필요합니다."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    # Register blueprints
    from app.auth import auth_bp
    from app.board import board_bp
    from app.core import core_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(board_bp)
    app.register_blueprint(core_bp)

    # Create tables
    import os as _os
    _instance = _os.path.join(os.path.dirname(basedir), 'instance')
    _os.makedirs(_instance, exist_ok=True)
    with app.app_context():
        from app.models import init_db
        init_db()

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return json.dumps({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return json.dumps({"error": "Internal server error"}), 500

    return app