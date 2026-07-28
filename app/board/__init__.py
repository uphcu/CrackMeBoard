from flask import Blueprint

board_bp = Blueprint("board", __name__, url_prefix="/board")

from app.board import routes