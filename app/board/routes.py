import bleach

from flask import (
    render_template, redirect, url_for, flash,
    request, jsonify, abort,
)
from flask_login import login_required, current_user

from app import db
from app.models import Post
from app.board import board_bp


ALLOWED_TAGS = [
    "b", "i", "u", "strong", "em", "p", "br", "ul", "ol", "li",
    "a", "pre", "code", "blockquote", "h1", "h2", "h3",
]


def _sanitize_html(text: str) -> str:
    return bleach.clean(text, tags=ALLOWED_TAGS, strip=True)


# ── List ──────────────────────────────────────────────

@board_bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    posts = (
        Post.query
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template("board/index.html", posts=posts)


# ── View ──────────────────────────────────────────────

@board_bp.route("/<int:post_id>")
def view(post_id: int):
    post = Post.query.get_or_404(post_id)
    return render_template("board/view.html", post=post)


# ── Create ────────────────────────────────────────────

@board_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        title = _sanitize_html((request.form.get("title") or "").strip())
        content = _sanitize_html(request.form.get("content") or "")

        if not title or len(title) > 200:
            return jsonify({"error": "제목은 1-200자로 입력하세요."}), 400
        if not content:
            return jsonify({"error": "내용을 입력하세요."}), 400

        post = Post(user_id=current_user.id, title=title, content=content)
        db.session.add(post)
        db.session.commit()

        return jsonify({"message": "게시글이 등록되었습니다.", "id": post.id}), 201

    return render_template("board/create.html")


# ── Update ────────────────────────────────────────────

@board_bp.route("/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def edit(post_id: int):
    post = Post.query.get_or_404(post_id)

    # IDOR protection: only author can edit
    if post.user_id != current_user.id:
        abort(403)

    if request.method == "POST":
        title = _sanitize_html((request.form.get("title") or "").strip())
        content = _sanitize_html(request.form.get("content") or "")

        if not title or len(title) > 200:
            return jsonify({"error": "标题은 1-200자로 입력하세요."}), 400

        post.title = title
        post.content = content
        db.session.commit()

        return jsonify({"message": "게시글이 수정되었습니다."}), 200

    return render_template("board/edit.html", post=post)


# ── Delete ────────────────────────────────────────────

@board_bp.route("/<int:post_id>/delete", methods=["POST"])
@login_required
def delete(post_id: int):
    post = Post.query.get_or_404(post_id)

    # IDOR protection
    if post.user_id != current_user.id:
        abort(403)

    db.session.delete(post)
    db.session.commit()

    return jsonify({"message": "게시글이 삭제되었습니다."}), 200