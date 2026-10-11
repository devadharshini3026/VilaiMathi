
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
import sqlite3
from functools import wraps
from datetime import date
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

app = Flask(__name__)
app.secret_key = "vilaimathi-local-demo-change-before-deployment"

DATABASE = "vilaimathi.db"


# ---------------- DATABASE ----------------

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                mobile TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                crop_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                expected_price REAL NOT NULL,
                quality TEXT NOT NULL,
                harvest_date TEXT NOT NULL,
                location TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)


# ---------------- LANGUAGE ----------------

def get_language():
    lang = request.args.get(
        "lang",
        session.get("lang", "en")
    )

    if lang not in ("en", "ta"):
        lang = "en"

    session["lang"] = lang
    return lang


# ---------------- LOGIN PROTECTION ----------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(
                url_for("login", lang=get_language())
            )
        return view(*args, **kwargs)

    return wrapped_view


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template(
        "index.html",
        lang=get_language()
    )


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    lang = get_language()
    message = ""
    success = False

    if request.method == "POST":
        role = request.form.get("role", "").strip()
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        location = request.form.get("location", "").strip()
        password = request.form.get("password", "")

        if role not in ("farmer", "buyer"):
            message = (
                "விவசாயி அல்லது வாங்குபவரைத் தேர்ந்தெடுக்கவும்."
                if lang == "ta"
                else "Please select Farmer or Buyer."
            )

        elif not name or not mobile or not location or not password:
            message = (
                "அனைத்து விவரங்களையும் நிரப்பவும்."
                if lang == "ta"
                else "Please fill in all fields."
            )

        elif not mobile.isdigit() or len(mobile) != 10:
            message = (
                "சரியான 10 இலக்க மொபைல் எண்ணை உள்ளிடவும்."
                if lang == "ta"
                else "Enter a valid 10-digit mobile number."
            )

        elif len(password) < 8:
            message = (
                "கடவுச்சொல் குறைந்தது 8 எழுத்துகள் இருக்க வேண்டும்."
                if lang == "ta"
                else "Password must be at least 8 characters."
            )

        else:
            try:
                with get_db_connection() as conn:
                    conn.execute("""
                        INSERT INTO users
                        (role, name, mobile, location, password_hash)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        role,
                        name,
                        mobile,
                        location,
                        generate_password_hash(password)
                    ))

                success = True
                message = (
                    "உங்கள் கணக்கு வெற்றிகரமாக உருவாக்கப்பட்டது!"
                    if lang == "ta"
                    else "Your account was created successfully!"
                )

            except sqlite3.IntegrityError:
                message = (
                    "இந்த மொபைல் எண் ஏற்கனவே பதிவு செய்யப்பட்டுள்ளது."
                    if lang == "ta"
                    else "This mobile number is already registered."
                )

            except sqlite3.Error:
                message = (
                    "பதிவு செய்ய முடியவில்லை. மீண்டும் முயற்சிக்கவும்."
                    if lang == "ta"
                    else "Registration failed. Please try again."
                )

    return render_template(
        "register.html",
        lang=lang,
        message=message,
        success=success
    )


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    lang = get_language()
    message = ""

    if request.method == "POST":
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")

        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE mobile = ?",
                (mobile,)
            ).fetchone()

        if user and check_password_hash(
            user["password_hash"], password
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["lang"] = lang

            return redirect(
                url_for("dashboard", lang=lang)
            )

        message = (
            "மொபைல் எண் அல்லது கடவுச்சொல் தவறாக உள்ளது."
            if lang == "ta"
            else "Incorrect mobile number or password."
        )

    return render_template(
        "login.html",
        lang=lang,
        message=message
    )


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():
    lang = get_language()

    with get_db_connection() as conn:
        user = conn.execute("""
            SELECT name, mobile, location, role
            FROM users
            WHERE id = ?
        """, (session["user_id"],)).fetchone()

        if user is None:
            session.clear()
            return redirect(url_for("login", lang=lang))

        crops = conn.execute("""
            SELECT *
            FROM crops
            WHERE user_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

    return render_template(
        "dashboard.html",
        lang=lang,
        user=user,
        crops=crops
    )


# ---------------- ADD CROP ----------------

@app.route("/crops/add", methods=["GET", "POST"])
@login_required
def add_crop():
    lang = get_language()

    with get_db_connection() as conn:
        user = conn.execute("""
            SELECT role, location
            FROM users
            WHERE id = ?
        """, (session["user_id"],)).fetchone()

    if user is None:
        session.clear()
        return redirect(url_for("login", lang=lang))

    if user["role"] != "farmer":
        return redirect(url_for("dashboard", lang=lang))

    message = ""

    if request.method == "POST":
        crop_name = request.form.get("crop_name", "").strip()
        category = request.form.get("category", "").strip()
        unit = request.form.get("unit", "").strip()
        quality = request.form.get("quality", "").strip()
        harvest_date = request.form.get("harvest_date", "").strip()
        location = request.form.get("location", "").strip()

        try:
            quantity = float(request.form.get("quantity", ""))
            expected_price = float(
                request.form.get("expected_price", "")
            )
        except (ValueError, TypeError):
            quantity = 0
            expected_price = 0

        valid_categories = {
            "Vegetables", "Fruits", "Grains", "Other"
        }
        valid_units = {"kg", "tonne"}
        valid_qualities = {"Standard", "Good", "Premium"}

        if (
            not crop_name
            or category not in valid_categories
            or unit not in valid_units
            or quality not in valid_qualities
            or not location
            or not harvest_date
        ):
            message = (
                "அனைத்து விவரங்களையும் சரியாக நிரப்பவும்."
                if lang == "ta"
                else "Please complete all fields correctly."
            )

        elif quantity <= 0 or expected_price <= 0:
            message = (
                "அளவும் விலையும் பூஜ்ஜியத்தை விட அதிகமாக இருக்க வேண்டும்."
                if lang == "ta"
                else "Quantity and price must be greater than zero."
            )

        elif harvest_date < date.today().isoformat():
            message = (
                "சரியான அறுவடை தேதியைத் தேர்ந்தெடுக்கவும்."
                if lang == "ta"
                else "Please choose a valid harvest date."
            )

        else:
            with get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO crops (
                        user_id, crop_name, category, quantity,
                        unit, expected_price, quality,
                        harvest_date, location
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session["user_id"],
                    crop_name,
                    category,
                    quantity,
                    unit,
                    expected_price,
                    quality,
                    harvest_date,
                    location
                ))

            flash(
                "விளைபொருள் வெற்றிகரமாக சேமிக்கப்பட்டது!"
                if lang == "ta"
                else "Crop added successfully!",
                "success"
            )

            return redirect(url_for("dashboard", lang=lang))

    return render_template(
        "add_crop.html",
        lang=lang,
        message=message,
        default_location=user["location"],
        today=date.today().isoformat()
    )


# ---------------- PRICE COMPARISON ----------------

@app.route("/compare-prices")
@login_required
def compare_prices():
    lang = get_language()
    crop_name = request.args.get("crop", "").strip()

    with get_db_connection() as conn:
        if crop_name:
            crops = conn.execute("""
                SELECT crops.*, users.name AS farmer_name
                FROM crops
                JOIN users ON crops.user_id = users.id
                WHERE LOWER(crops.crop_name) = LOWER(?)
                ORDER BY crops.expected_price ASC
            """, (crop_name,)).fetchall()
        else:
            crops = conn.execute("""
                SELECT crops.*, users.name AS farmer_name
                FROM crops
                JOIN users ON crops.user_id = users.id
                ORDER BY crops.crop_name ASC,
                         crops.expected_price ASC
            """).fetchall()

        crop_names = conn.execute("""
            SELECT DISTINCT crop_name
            FROM crops
            ORDER BY crop_name ASC
        """).fetchall()

    return render_template(
        "compare_prices.html",
        lang=lang,
        crops=crops,
        crop_names=crop_names,
        selected_crop=crop_name
    )


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    lang = get_language()
    session.clear()
    return redirect(url_for("home", lang=lang))


# ---------------- RUN APP ----------------

if __name__ == "__main__":
    create_table()
    app.run(debug=True)
