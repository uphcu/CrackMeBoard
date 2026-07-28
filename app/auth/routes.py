import logging
from datetime import datetime, timezone, timedelta

import pyotp
import qrcode
import bleach
from io import BytesIO
from base64 import b64encode

from flask import (
    render_template, redirect, url_for, flash,
    request, session, jsonify, abort,
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_limiter import util

from app import db, limiter
from app.models import User, LoginLog
from app.auth import auth_bp

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────

def _log_login(user_id, success, reason=None):
    log = LoginLog(
        user_id=user_id,
        ip_address=request.remote_addr or "0.0.0.0",
        user_agent=request.headers.get("User-Agent", "")[:500],
        success=success,
        failure_reason=reason,
    )
    db.session.add(log)
    db.session.commit()


def _rate_limit_key():
    """Key: ip + input_username"""
    username = request.form.get("username", request.form.get("email", "unknown"))
    return f"login:{request.remote_addr}:{username}"


# ── Register ──────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute", key_func=_rate_limit_key)
def register():
    if current_user.is_authenticated:
        return redirect(url_for("board.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        errors = []
        if not email or "@" not in email or len(email) > 255:
            errors.append("올바른 이메일을 입력하세요.")
        if not username or len(username) < 3 or len(username) > 50:
            errors.append("사용자명은 3-50자로 입력하세요.")
        if len(password) < 8:
            errors.append("비밀번호는 8자 이상이어야 합니다.")

        if User.query.filter((User.email == email) | (User.username == username)).first():
            errors.append("이미 존재하는 이메일 또는 사용자명입니다.")

        if errors:
            return json.dumps({"errors": errors}), 400

        user = User(email=email, username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return json.dumps({"message": "회원가입이 완료되었습니다."}), 201

    return render_template("auth/register.html")


# ── Login ─────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", key_func=_rate_limit_key)
def login():
    if current_user.is_authenticated:
        return redirect(url_for("board.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()

        # User not found
        if not user:
            _log_login(None, False, "user_not_found")
            return json.dumps({"error": "이메일 또는 비밀번호가 올바르지 않습니다."}), 401

        # Password check
        if not user.check_password(password):
            _log_login(user.id, False, "wrong_password")
            return json.dumps({"error": "이메일 또는 비밀번호가 올바르지 않습니다."}), 401

        # 2FA check
        if user.totp_enabled:
            # Require OTP
            totp_code = (request.form.get("totp_code") or "").strip()
            if not totp_code or not pyotp.TOTP(user.totp_secret).verify(totp_code):
                _log_login(user.id, False, "2fa_failed")
                return json.dumps({"error": "2FA 코드가 올바르지 않습니다.", "require_2fa": True}), 401

        # Success
        login_user(user, remember=True, duration=timedelta(hours=12))
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
        _log_login(user.id, True, None)

        return json.dumps({"message": "로그인 성공", "next": url_for("board.index")}), 200

    return render_template("auth/login.html")


# ── Logout ────────────────────────────────────────────

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("auth.login"))


# ── 2FA Setup ─────────────────────────────────────────

@auth_bp.route("/2fa/setup", methods=["GET", "POST"])
@login_required
def setup_2fa():
    if request.method == "GET":
        if not current_user.totp_secret:
            current_user.totp_secret = pyotp.random_base32()
            db.session.commit()

        totp = pyotp.TOTP(current_user.totp_secret)
        uri = totp.provisioning_uri(
            name=current_user.username,
            issuer_name="CrackMeBoard",
        )

        # Generate QR code
        img = qrcode.make(uri)
        buf = BytesIO()
        img.save(buf, format="PNG")
        data = b64encode(buf.getvalue()).decode()

        return render_template("auth/setup_2fa.html", qr_data=data, secret=current_user.totp_secret)

    # POST: verify and enable
    code = (request.form.get("code") or "").strip()
    totp = pyotp.TOTP(current_user.totp_secret)

    if totp.verify(code):
        current_user.totp_enabled = True
        db.session.commit()
        return json.dumps({"message": "2차 인증이 활성화되었습니다."}), 200
    else:
        return json.dumps({"error": "코드가 올바르지 않습니다."}), 400


# ── Honeypot Routes ───────────────────────────────────

HONEYPOT_PATHS = ["/admin.php", "/wp-admin", "/phpmyadmin", "/.env", "/api/v1/admin"]


@auth_bp.route("/honeypot/<path:path>")
def honeypot(path):
    """Fake admin paths — log and block"""
    logger.warning(f"Honeypot hit: /{path} from {request.remote_addr}")
    abort(404)  # Return 404, don't reveal it's an honeypot