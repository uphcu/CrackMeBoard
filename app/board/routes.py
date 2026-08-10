import bleach

from flask import (
    render_template, redirect, url_for, flash,
    request, jsonify, abort,
)
from flask_login import login_required, current_user

from app import db
from app.models import Post, Comment
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
    q = (request.args.get("q") or "").strip()

    query = Post.query
    if q:
        query = query.filter(
            (Post.title.contains(q)) | (Post.content.contains(q))
        )

    posts = (
        query
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template("board/index.html", posts=posts, q=q)


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


# ── Comments ───────────────────────────────────────────

@board_bp.route("/<int:post_id>/comments", methods=["GET"])
def list_comments(post_id: int):
    post = Post.query.get_or_404(post_id)
    comments = post.comments.order_by(Comment.created_at.asc()).all()
    return jsonify([{
        "id": c.id,
        "author": c.author.username,
        "content": c.content,
        "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
    } for c in comments])


@board_bp.route("/<int:post_id>/comments", methods=["POST"])
@login_required
def create_comment(post_id: int):
    post = Post.query.get_or_404(post_id)
    content = _sanitize_html((request.form.get("content") or "").strip())

    if not content or len(content) > 1000:
        return jsonify({"error": "댓글은 1-1000자로 입력하세요."}), 400

    comment = Comment(post_id=post.id, user_id=current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        "id": comment.id,
        "author": current_user.username,
        "content": comment.content,
        "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M"),
    }), 201


@board_bp.route("/<int:post_id>/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_comment(post_id: int, comment_id: int):
    comment = Comment.query.get_or_404(comment_id)

    if comment.post_id != post_id or comment.user_id != current_user.id:
        abort(403)

    db.session.delete(comment)
    db.session.commit()

    return jsonify({"message": "댓글이 삭제되었습니다."}), 200