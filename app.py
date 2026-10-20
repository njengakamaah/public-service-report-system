import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, abort, flash, g, redirect, render_template,
    request, send_from_directory, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "service_requests.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_BYTES = 3 * 1024 * 1024  # 3 MB

app = Flask(__name__)
# Set a real random SECRET_KEY in your environment before deployment.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "dev-only-change-this-key"
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


def get_db():
    """Return one SQLite connection per request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    """Close the database connection after the request ends."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables needed by the application."""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'citizen'
                CHECK (role IN ('citizen', 'admin')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS service_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            image_filename TEXT,
            status TEXT NOT NULL DEFAULT 'Pending'
                CHECK (status IN ('Pending', 'In Progress', 'Resolved')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_by INTEGER NOT NULL,
            note TEXT,
            changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES service_requests(id),
            FOREIGN KEY (changed_by) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_requests_user
            ON service_requests(user_id);
        CREATE INDEX IF NOT EXISTS idx_requests_status
            ON service_requests(status);
    """)
    db.commit()
    db.close()

# Ensure database tables exist when the app starts on Render.
init_db()

def login_required(view):
    """Allow access only to signed-in users."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view


def admin_required(view):
    """Allow access only to signed-in administrators."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            abort(403)
        return view(**kwargs)
    return wrapped_view


@app.before_request
def load_logged_in_user():
    """Load the current user's database record for each request."""
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT id, full_name, email, role FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()


@app.context_processor
def inject_year():
    """Make the current year available to all templates."""
    return {"current_year": datetime.now().year}


@app.route("/")
def index():
    """Public landing page."""
    return render_template("index.html")


@app.route("/register", methods=("GET", "POST"))
def register():
    """Create a citizen account."""
    if g.user is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        error = None

        if len(full_name) < 2:
            error = "Enter your full name."
        elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            error = "Enter a valid email address."
        elif len(password) < 8:
            error = "Your password must contain at least 8 characters."
        elif password != confirm_password:
            error = "The passwords do not match."

        if error is None:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
                    (full_name, email, generate_password_hash(password))
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = "An account with that email already exists."

        if error:
            flash(error, "danger")
        else:
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    """Authenticate a user using their email and password."""
    if g.user is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))

    return render_template("login.html")
@app.route("/setup-admin", methods=("GET", "POST"))
def setup_admin():
    """Allow one-time admin creation using a secret setup token."""
    setup_token = os.environ.get("ADMIN_SETUP_TOKEN")

    # Disable setup if the environment token is missing.
    if not setup_token:
        abort(404)

    db = get_db()

    # Only allow setup when no administrator exists.
    existing_admin = db.execute(
        "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
    ).fetchone()

    if existing_admin:
        abort(404)

    if request.method == "POST":
        submitted_token = request.form.get("setup_token", "")
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not secrets.compare_digest(submitted_token, setup_token):
            abort(403)

        if len(full_name) < 2 or "@" not in email:
            flash("Enter a valid name and email.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        else:
            try:
                db.execute(
                    """INSERT INTO users
                       (full_name, email, password_hash, role)
                       VALUES (?, ?, ?, 'admin')""",
                    (full_name, email, generate_password_hash(password))
                )
                db.commit()
                flash(
                    "Administrator created. Please log in.",
                    "success"
                )
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("An account with that email already exists.", "danger")

    return render_template("admin_setup.html")

@app.post("/logout")
@login_required
def logout():
    """End the current session."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Show the citizen's own reports or the admin overview."""
    db = get_db()
    if g.user["role"] == "admin":
        counts = {
            "open": db.execute(
                "SELECT COUNT(*) FROM service_requests WHERE status != 'Resolved'"
            ).fetchone()[0],
            "resolved": db.execute(
                "SELECT COUNT(*) FROM service_requests WHERE status = 'Resolved'"
            ).fetchone()[0],
            "total": db.execute(
                "SELECT COUNT(*) FROM service_requests"
            ).fetchone()[0],
        }
        reports = db.execute("""
            SELECT r.*, u.full_name AS citizen_name, u.email AS citizen_email
            FROM service_requests r
            JOIN users u ON u.id = r.user_id
            ORDER BY r.created_at DESC
        """).fetchall()
        return render_template("admin_dashboard.html", reports=reports, counts=counts)

    reports = db.execute("""
        SELECT * FROM service_requests
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (g.user["id"],)).fetchall()
    return render_template("citizen_dashboard.html", reports=reports)


def allowed_extension(filename):
    """Check that a filename has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file_storage):
    """Validate an image's extension and actual image content before saving."""
    if not file_storage or not file_storage.filename:
        return None

    original_name = secure_filename(file_storage.filename)
    if not original_name or not allowed_extension(original_name):
        raise ValueError("Use a PNG, JPG, JPEG, or WEBP image.")

    try:
        # Pillow checks the file content rather than trusting the filename alone.
        image = Image.open(file_storage.stream)
        image.verify()
        file_storage.stream.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("The uploaded file is not a valid image.")

    extension = original_name.rsplit(".", 1)[1].lower()
    stored_name = f"{secrets.token_hex(16)}.{extension}"
    file_storage.save(UPLOAD_FOLDER / stored_name)
    return stored_name


@app.route("/requests/new", methods=("GET", "POST"))
@login_required
def new_request():
    """Let a citizen submit a community service request."""
    if g.user["role"] != "citizen":
        flash("Administrators use the dashboard to manage reports.", "info")
        return redirect(url_for("dashboard"))

    categories = [
        "Broken streetlight", "Water issue", "Garbage collection",
        "Road damage", "Drainage issue", "Other"
    ]

    if request.method == "POST":
        category = request.form.get("category", "")
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        image_file = request.files.get("image")
        error = None
        image_filename = None

        if category not in categories:
            error = "Choose a valid category."
        elif not location or len(location) > 200:
            error = "Enter a location of up to 200 characters."
        elif len(description) < 10 or len(description) > 2000:
            error = "Description must be between 10 and 2,000 characters."

        if error is None:
            try:
                image_filename = save_uploaded_image(image_file)
            except ValueError as exc:
                error = str(exc)

        if error:
            flash(error, "danger")
        else:
            db = get_db()
            # Generate a readable reference number; retry if it already exists.
            while True:
                reference = "PSR-" + secrets.token_hex(4).upper()
                exists = db.execute(
                    "SELECT 1 FROM service_requests WHERE reference = ?",
                    (reference,)
                ).fetchone()
                if not exists:
                    break

            cursor = db.execute("""
                INSERT INTO service_requests
                    (reference, user_id, category, location, description, image_filename)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (reference, g.user["id"], category, location, description, image_filename))
            db.commit()

            db.execute("""
                INSERT INTO status_history
                    (request_id, old_status, new_status, changed_by, note)
                VALUES (?, NULL, 'Pending', ?, 'Request submitted')
            """, (cursor.lastrowid, g.user["id"]))
            db.commit()

            flash(f"Request submitted. Your reference is {reference}.", "success")
            return redirect(url_for("dashboard"))

    return render_template("new_request.html", categories=categories)


@app.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    """Show a report only to its owner or an administrator."""
    db = get_db()
    report = db.execute("""
        SELECT r.*, u.full_name AS citizen_name, u.email AS citizen_email
        FROM service_requests r
        JOIN users u ON u.id = r.user_id
        WHERE r.id = ?
    """, (request_id,)).fetchone()

    if report is None:
        abort(404)
    if g.user["role"] != "admin" and report["user_id"] != g.user["id"]:
        abort(403)

    history = db.execute("""
        SELECT h.*, u.full_name AS changed_by_name
        FROM status_history h
        JOIN users u ON u.id = h.changed_by
        WHERE h.request_id = ?
        ORDER BY h.changed_at DESC, h.id DESC
    """, (request_id,)).fetchall()

    return render_template("request_detail.html", report=report, history=history)


@app.post("/admin/requests/<int:request_id>/status")
@admin_required
def update_status(request_id):
    """Allow an administrator to change a report's status."""
    allowed_statuses = {"Pending", "In Progress", "Resolved"}
    new_status = request.form.get("status", "")
    note = request.form.get("note", "").strip()[:500]

    if new_status not in allowed_statuses:
        flash("Choose a valid status.", "danger")
        return redirect(url_for("dashboard"))

    db = get_db()
    report = db.execute(
        "SELECT * FROM service_requests WHERE id = ?", (request_id,)
    ).fetchone()

    if report is None:
        abort(404)

    old_status = report["status"]
    if old_status != new_status:
        db.execute("""
            UPDATE service_requests
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, request_id))
        db.execute("""
            INSERT INTO status_history
                (request_id, old_status, new_status, changed_by, note)
            VALUES (?, ?, ?, ?, ?)
        """, (request_id, old_status, new_status, g.user["id"], note or None))
        db.commit()
        flash("Request status updated.", "success")
    else:
        flash("The request already has that status.", "info")

    return redirect(url_for("dashboard"))


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_image(filename):
    """Serve an uploaded image only to its owner or an administrator."""
    db = get_db()
    report = db.execute(
        "SELECT user_id FROM service_requests WHERE image_filename = ?",
        (filename,)
    ).fetchone()
    if report is None:
        abort(404)
    if g.user["role"] != "admin" and report["user_id"] != g.user["id"]:
        abort(403)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The page or request could not be found."), 404


@app.errorhandler(413)
def file_too_large(_error):
    flash("Image is too large. Maximum upload size is 3 MB.", "danger")
    return redirect(request.referrer or url_for("new_request"))


@app.cli.command("init-db")
def init_db_command():
    """Run `flask --app app init-db` to create database tables."""
    init_db()
    print("Database tables are ready.")


@app.cli.command("create-admin")
def create_admin_command():
    """Create an administrator interactively without hard-coding a password."""
    import getpass

    full_name = input("Administrator full name: ").strip()
    email = input("Administrator email: ").strip().lower()
    password = getpass.getpass("Administrator password (8+ characters): ")
    confirm = getpass.getpass("Confirm password: ")

    if len(full_name) < 2 or "@" not in email:
        print("Enter a valid name and email.")
        return
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return
    if password != confirm:
        print("Passwords do not match.")
        return

    init_db()
    db = sqlite3.connect(DATABASE)
    try:
        db.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
            (full_name, email, generate_password_hash(password))
        )
        db.commit()
        print("Administrator account created.")
    except sqlite3.IntegrityError:
        print("An account with that email already exists.")
    finally:
        db.close()


# Initialize the database when the app is first run directly.
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
