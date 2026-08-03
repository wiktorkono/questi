import random
import sqlite3
import string
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

DB_FILE = "questi.db"
app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL;")
        g.db.execute("PRAGMA busy_timeout=5000;")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS boards (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS board_access (
            user_id INTEGER NOT NULL,
            board_id TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (board_id) REFERENCES boards (id),
            PRIMARY KEY (user_id, board_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id TEXT NOT NULL,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (board_id) REFERENCES boards (id)
        )
        """
    )

    existing = conn.execute("SELECT 1 FROM users WHERE username = ?", ("demo",)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("demo", generate_password_hash("demo")),
        )
        print("Seeded default user 'demo' with password 'demo'. Change this before exposing the server publicly.")

    conn.commit()
    conn.close()


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth:
            return jsonify({"error": "Authentication required."}), 401

        db = get_db()
        user = db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (auth.username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], auth.password):
            return jsonify({"error": "Invalid credentials."}), 401

        g.user_id = user["id"]
        return f(*args, **kwargs)

    return wrapper


def generate_board_id(db):
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(random.choices(alphabet, k=8))
        exists = db.execute("SELECT 1 FROM boards WHERE id = ?", (candidate,)).fetchone()
        if not exists:
            return candidate


def user_has_access(db, user_id, board_id):
    row = db.execute(
        "SELECT 1 FROM board_access WHERE user_id = ? AND board_id = ?", (user_id, board_id)
    ).fetchone()
    return row is not None


@app.route("/boards", methods=["GET"])
@require_auth
def list_boards():
    db = get_db()
    rows = db.execute(
        """
        SELECT boards.id, boards.name FROM boards
        JOIN board_access ON board_access.board_id = boards.id
        WHERE board_access.user_id = ?
        ORDER BY boards.id
        """,
        (g.user_id,),
    ).fetchall()
    return jsonify([{"id": r["id"], "name": r["name"]} for r in rows])


@app.route("/boards", methods=["POST"])
@require_auth
def create_board():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Board name is required."}), 400

    db = get_db()
    board_id = generate_board_id(db)

    try:
        db.execute("INSERT INTO boards (id, name) VALUES (?, ?)", (board_id, name))
        db.execute(
            "INSERT INTO board_access (user_id, board_id) VALUES (?, ?)", (g.user_id, board_id)
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400

    return jsonify({"id": board_id, "name": name}), 201


@app.route("/boards/<board_id>/tasks", methods=["GET"])
@require_auth
def list_tasks(board_id):
    db = get_db()
    if not user_has_access(db, g.user_id, board_id):
        return jsonify({"error": "Board not found or access denied."}), 404

    rows = db.execute(
        "SELECT id, title, done FROM tasks WHERE board_id = ? ORDER BY id", (board_id,)
    ).fetchall()
    return jsonify([{"id": r["id"], "title": r["title"], "done": bool(r["done"])} for r in rows])


@app.route("/boards/<board_id>/tasks", methods=["POST"])
@require_auth
def create_task(board_id):
    db = get_db()
    if not user_has_access(db, g.user_id, board_id):
        return jsonify({"error": "Board not found or access denied."}), 404

    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Task title is required."}), 400

    cursor = db.execute("INSERT INTO tasks (board_id, title) VALUES (?, ?)", (board_id, title))
    db.commit()
    return jsonify({"id": cursor.lastrowid, "title": title, "done": False}), 201


@app.route("/boards/<board_id>/tasks/<int:task_id>/toggle", methods=["POST"])
@require_auth
def toggle_task(board_id, task_id):
    db = get_db()
    if not user_has_access(db, g.user_id, board_id):
        return jsonify({"error": "Board not found or access denied."}), 404

    row = db.execute(
        "SELECT done FROM tasks WHERE id = ? AND board_id = ?", (task_id, board_id)
    ).fetchone()
    if row is None:
        return jsonify({"error": "Task not found."}), 404

    new_done = 0 if row["done"] else 1
    db.execute("UPDATE tasks SET done = ? WHERE id = ?", (new_done, task_id))
    db.commit()
    return jsonify({"id": task_id, "done": bool(new_done)})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=3007)