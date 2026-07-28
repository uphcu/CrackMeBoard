from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email: str = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username: str = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash: str = db.Column(db.String(255), nullable=False)
    totp_secret: str = db.Column(db.String(32), nullable=True)
    totp_enabled: bool = db.Column(db.Boolean, default=False)
    created_at: datetime = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_login: datetime = db.Column(db.DateTime, nullable=True)

    # Relations
    login_logs = db.relationship("LoginLog", backref="user", lazy="dynamic")
    posts = db.relationship("Post", backref="author", lazy="dynamic")

    def set_password(self, password: str):
        """bcrypt hashing"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class LoginLog(db.Model):
    __tablename__ = "login_logs"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    ip_address: str = db.Column(db.String(45), nullable=False)
    user_agent: str = db.Column(db.String(512), nullable=True)
    success: bool = db.Column(db.Boolean, default=False)
    failure_reason: str = db.Column(db.String(100), nullable=True)
    created_at: datetime = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Post(db.Model):
    __tablename__ = "posts"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title: str = db.Column(db.String(200), nullable=False)
    content: str = db.Column(db.Text, nullable=False)
    created_at: datetime = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def init_db():
    """Create all tables (SQLite compatible)."""
    from app import db as _db
    import os as _os
    # Only create tables if DB file doesn't exist (prevent multi-worker race)
    db_path = _db.engine.url.database
    if db_path and _os.path.exists(db_path):
        return  # DB already exists, skip creation
    _db.create_all()