from flask import Flask, request, jsonify, g
from flask_cors import CORS
import mysql.connector
import bcrypt
import jwt
import datetime
import random
from collections import OrderedDict
import os
import logging

# Google ID token verification
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from flask_mail import Mail, Message

import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from db import compat_connect, init_db_pool
import auth
import storage
from email_worker import email_worker

app = Flask(__name__)

# Initialize pool early
init_db_pool()

# Configure app from central config
app.config.update(
    MAIL_SERVER=config.MAIL_SERVER,
    MAIL_PORT=config.MAIL_PORT,
    MAIL_USE_TLS=config.MAIL_USE_TLS,
    MAIL_USERNAME=config.MAIL_USERNAME,
    MAIL_PASSWORD=config.MAIL_PASSWORD,
    MAIL_DEFAULT_SENDER=config.MAIL_DEFAULT_SENDER,
    MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
)

mail = Mail(app)

# CORS: restrict origins
CORS(app, origins=config.CORS_ORIGINS)

# Logging
logging.basicConfig(level=logging.DEBUG if config.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

# Expose DEBUG toggles
DEBUG = config.DEBUG
DEBUG_SHOW_OTP = config.DEBUG_SHOW_OTP

# Host/Port for local run
PORT = int(os.environ.get("PORT", 5000))
HOST = os.environ.get("HOST", "0.0.0.0")

# Ensure Flask SECRET_KEY set
app.config['SECRET_KEY'] = config.SECRET_KEY

# Monkeypatch mysql.connector.connect to use pooled connections (compatibility shim)
mysql.connector.connect = compat_connect

# Rate limiting
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["200 per day", "50 per hour"]) 


def validate_required_env():
    """Stop startup if critical environment variables are missing in production."""
    missing = []
    if not config.SECRET_KEY:
        missing.append("SECRET_KEY")
    if not config.GOOGLE_CLIENT_ID:
        missing.append("GOOGLE_CLIENT_ID")

    if missing:
        # In debug mode allow missing (helpful for local testing), otherwise exit with message
        if DEBUG:
            app.logger.warning("Missing environment variables (allowed in DEBUG): %s", ", ".join(missing))
        else:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


# Validate env as soon as module is imported (WSGI servers will import module)
try:
    validate_required_env()
except Exception:
    # If imported in runtime where we shouldn't exit the process silently, re-raise
    raise


def generate_unique_user_id(cursor):
    """Generate a unique random 11-digit user ID"""
    max_attempts = 100  # Prevent infinite loop
    for _ in range(max_attempts):
        # Generate random 11-digit number (10000000000 to 99999999999)
        user_id = random.randint(10000000000, 99999999999)
        
        # Check if ID already exists
        cursor.execute("SELECT id FROM signin WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            return user_id
    
    # If we couldn't find a unique ID after max attempts, raise an error
    raise Exception("Unable to generate unique user ID after multiple attempts")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json or {}
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    email = data.get("email")
    password = data.get("password")
    user_role = data.get("user", "patient")  # Default to "patient" if not provided
    dob = data.get("dob")  # Date of birth (format: YYYY-MM-DD)
    gender = data.get("gender")  # Gender field

    if not all([first_name, last_name, email, password]):
        return jsonify({"error": "First name, last name, email and password are required"}), 400

    conn = compat_connect()
    cursor = conn.cursor(dictionary=True)

    # Check if email exists
    cursor.execute("SELECT id FROM signin WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Email already exists"}), 400

    # Generate unique 11-digit user ID
    try:
        user_id = generate_unique_user_id(cursor)
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to generate user ID. Please try again."}), 500

    # Hash password  
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode('utf-8')

    # Insert into DB with explicit ID, user role and auth_provider
    try:
        cursor.execute(
            "INSERT INTO signin (id, first_name, last_name, email, password_hash, `user`, auth_provider) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, first_name.strip(), last_name.strip(), email.strip(), hashed_password, user_role, 'local')
        )
    except Exception:
        cursor.execute(
            "INSERT INTO signin (id, first_name, last_name, email, password_hash, `user`) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, first_name.strip(), last_name.strip(), email.strip(), hashed_password, user_role)
        )
    conn.commit()

    # Insert user details with dob, gender, calculated age, and default language
    try:
        age = None
        if dob:
            dob_date = datetime.datetime.strptime(dob.strip(), "%Y-%m-%d").date()
            today = datetime.datetime.now().date()
            age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
        
        cursor.execute("""
            INSERT INTO user_details (user_id, dob, gender, age, language)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, dob.strip() if dob else None, gender.strip() if gender else None, age, "English"))
        conn.commit()
    except Exception as e:
        print(f"Warning: Failed to insert user details: {e}")
        pass
    
    cursor.close()
    conn.close()

    # Generate JWT token
    token = jwt.encode(
        {
            "user_id": user_id,
            "email": email.strip(),
            "user": user_role,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        },
        config.SECRET_KEY,
        algorithm="HS256",
    )

    return jsonify({
        "message": "Signup successful",
        "token": token,
        "user_id": str(user_id),
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.strip(),
        "user": user_role
    }), 201

# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not all([email, password]):
        return jsonify({"error": "Email and password required"}), 400

    try:
        conn = compat_connect()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM signin WHERE email = %s", (email,))
        user = cursor.fetchone()

        # Normalize stored password hash if it's binary (migration convenience)
        try:
            if user and isinstance(user.get("password_hash"), (bytes, bytearray)):
                normalized = user.get("password_hash").decode("utf-8")
                ucur = conn.cursor()
                ucur.execute("UPDATE signin SET password_hash = %s WHERE id = %s", (normalized, user.get("id")))
                conn.commit()
                ucur.close()
                user["password_hash"] = normalized
        except Exception:
            # Non-fatal: continue using the value as-is
            pass

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Login database error: {e}")
        return jsonify({"error": f"Database connection error: {str(e)}"}), 500

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return jsonify({"error": "Invalid email or password"}), 401

    # Generate JWT Token
    token = jwt.encode({
        "user_id": user["id"],
        "email": user["email"],
        "user": user.get("user"),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }, config.SECRET_KEY, algorithm="HS256")

    return jsonify({
        "token": token,
        "user_id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"]
        ,"user": user.get("user")
    }), 200


# ---------------- GOOGLE AUTH ----------------
@app.route("/auth/google", methods=["POST"])
def auth_google():
    data = request.json or {}
    id_token_str = data.get("id_token")
    if not id_token_str:
        return jsonify({"error": "id_token is required"}), 400

    if not config.GOOGLE_CLIENT_ID:
        return jsonify({"error": "Server misconfiguration: GOOGLE_CLIENT_ID not set"}), 500

    # Verify ID token
    try:
        idinfo = id_token.verify_oauth2_token(id_token_str, google_requests.Request(), audience=config.GOOGLE_CLIENT_ID)
    except Exception as e:
        return jsonify({"error": "Invalid or expired ID token"}), 401

    email = idinfo.get("email")
    email_verified = idinfo.get("email_verified")
    google_sub = idinfo.get("sub")
    first_name = idinfo.get("given_name")
    last_name = idinfo.get("family_name")

    if not email or not google_sub:
        return jsonify({"error": "Email or subject missing in ID token"}), 400

    # Require verified email for production safety
    if not email_verified:
        return jsonify({"error": "Email not verified by Google"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Check if user exists
    cursor.execute("SELECT * FROM signin WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        # Existing user: allow login regardless of auth_provider (email ownership verified)
        user_id = user["id"]
        user_role = user.get("user") or "patient"

        # If we don't have google_sub stored for a google user, store it
        try:
            if user.get("auth_provider") == "google" and not user.get("google_sub"):
                ucur = conn.cursor()
                ucur.execute("UPDATE signin SET google_sub = %s WHERE id = %s", (google_sub, user_id))
                conn.commit()
                ucur.close()
        except Exception:
            pass

    else:
        # Create a new user record for this Google user
        try:
            user_id = generate_unique_user_id(cursor)
        except Exception as e:
            cursor.close()
            conn.close()
            return jsonify({"error": "Failed to generate user ID"}), 500

        try:
            # Insert user with auth_provider = 'google', password_hash left NULL
            icer = conn.cursor()
            icer.execute(
                "INSERT INTO signin (id, first_name, last_name, email, password_hash, `user`, auth_provider, google_sub) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, first_name, last_name, email, None, 'patient', 'google', google_sub)
            )
            conn.commit()
            icer.close()
            user_role = 'patient'
        except Exception as e:
            cursor.close()
            conn.close()
            return jsonify({"error": "Failed to create user"}), 500

    # Issue JWT using existing SECRET_KEY and expiry logic
    token = jwt.encode({
        "user_id": user_id,
        "email": email,
        "user": user.get("user") if user else user_role,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }, config.SECRET_KEY, algorithm="HS256")

    cursor.close()
    conn.close()

    return jsonify({
        "token": token,
        "user_id": user_id,
        "first_name": first_name or (user.get("first_name") if user else ""),
        "last_name": last_name or (user.get("last_name") if user else ""),
        "email": email,
        "user": user.get("user") if user else user_role
    }), 200

# ---------------- ADD USER DETAILS ----------------
@app.route("/user/details", methods=["POST"])
def add_user_details():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]  # remove "Bearer"
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))  # Ensure it's an integer
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    data = request.json
    dob = data.get("dob")
    gender = data.get("gender")
    age = data.get("age")
    language = data.get("language")

    if not all([dob, gender, age, language]):
        return jsonify({"error": "All fields are required"}), 400

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Check if details already exist for this user
    cursor.execute("SELECT * FROM user_details WHERE user_id = %s", (user_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Details already exist"}), 400

    # Insert new details (username removed)
    cursor.execute("""
        INSERT INTO user_details (user_id, dob, gender, age, language)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, dob, gender, age, language))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "User details added successfully"}), 201

# ---------------- SEARCH USER BY ID ----------------
@app.route("/search/user/<int:user_id>", methods=["GET"])
def search_user_by_id(user_id):
    """Search for a user by their ID (from signin table)"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="graftpredict"
        )
        cursor = conn.cursor(dictionary=True)

        # Query from signin table only (for user search)
        cursor.execute("""
            SELECT id, first_name, last_name, email, user
            FROM signin
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"user_details": user}), 200
    except Exception as e:
        print(f"Error searching user: {e}")
        return jsonify({"error": "Server error"}), 500

# ---------------- GET USER DETAILS ----------------
@app.route("/user/details", methods=["GET"])
def get_user_details():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.id, s.first_name, s.last_name, s.email, s.user,
               ud.dob, ud.gender, ud.age, ud.language,
               ud.created_at, ud.updated_at
        FROM signin s
        LEFT JOIN user_details ud ON s.id = ud.user_id
        WHERE s.id = %s
    """, (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Convert dates to string (YYYY-MM-DD)
    dob = user["dob"].strftime("%Y-%m-%d") if user["dob"] else None
    created_at = user["created_at"].strftime("%Y-%m-%d %H:%M:%S") if user["created_at"] else None
    updated_at = user["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if user["updated_at"] else None

    # Maintain order explicitly
    ordered_response = OrderedDict([
        ("id", user["id"]),
        ("first_name", user["first_name"]),
        ("last_name", user["last_name"]),
        ("email", user["email"]),
        ("user", user.get("user")),
        ("dob", dob),
        ("gender", user["gender"]),
        ("age", user["age"]),
        ("language", user["language"]),
        ("created_at", created_at),
        ("updated_at", updated_at)
    ])

    return jsonify({"user_details": ordered_response}), 200

# ---------------- UPDATE USER DETAILS ----------------
@app.route("/user/details/update", methods=["PUT"])
def update_user_details():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    data = request.json
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    dob = data.get("dob")
    gender = data.get("gender")
    age = data.get("age")
    language = data.get("language")

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    logger.debug("/user/details/update called for user_id=%s payload=%s", user_id, data)

    try:
        # Update user basic info
        cursor.execute("""
            UPDATE signin 
            SET first_name = %s, last_name = %s 
            WHERE id = %s
        """, (first_name, last_name, user_id))

        # Update or insert user details
        cursor.execute("SELECT * FROM user_details WHERE user_id = %s", (user_id,))
        if cursor.fetchone():
            # Update existing details
            cursor.execute("""
                UPDATE user_details 
                SET dob = %s, gender = %s, age = %s, language = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (dob, gender, age, language, user_id))
        else:
            # Insert new details
            cursor.execute("""
                INSERT INTO user_details (user_id, dob, gender, age, language)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, dob, gender, age, language))

        conn.commit()

        # Fetch updated row for verification (helpful in DEBUG)
        cursor.execute(
            """
            SELECT s.id, s.first_name, s.last_name, s.email, ud.dob, ud.gender, ud.age, ud.language
            FROM signin s
            LEFT JOIN user_details ud ON s.id = ud.user_id
            WHERE s.id = %s
            """,
            (user_id,)
        )
        updated = cursor.fetchone()

    except Exception as e:
        logger.exception("Failed to update user details for user_id=%s: %s", user_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to update user details", "detail": str(e)}), 500

    cursor.close()
    conn.close()

    if DEBUG:
        return jsonify({"message": "User details updated successfully", "updated": updated}), 200

    return jsonify({"message": "User details updated successfully"}), 200

# ---------------- REPORTS ----------------
@app.route("/reports", methods=["POST"])
def create_report():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))
        email_from_token = decoded.get("email")
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    is_multipart = request.content_type and request.content_type.lower().startswith("multipart/")
    payload = request.form if is_multipart else (request.json or {})

    name = payload.get("name")
    age = payload.get("age")
    gender = payload.get("gender")
    affected_side = payload.get("affected_side")
    affected_date = payload.get("affected_date")
    height = payload.get("height")
    weight = payload.get("weight")
    bmi = payload.get("bmi")
    leg_length = payload.get("leg_length")
    thigh_length = payload.get("thigh_length")
    circumfrence_thigh = payload.get("circumfrence_thigh")
    posterior_st = payload.get("posterior_st")
    posterior_gracilis = payload.get("posterior_gracilis")
    lateral_st = payload.get("lateral_st")
    lateral_gracilis = payload.get("lateral_gracilis")
    graft_diameter_1 = payload.get("graft_diameter_1")
    graft_diameter_2 = payload.get("graft_diameter_2")
    hamstring_autograft = payload.get("hamstring_autograft")
    quadriceps_tendon_diameter = payload.get("quadriceps_tendon_diameter")
    minimum_st_length = payload.get("minimum_st_length")
    predicted_st_value = payload.get("predicted_st_value")
    gracilis_length = payload.get("gracilis_length")

    pdf_report_bytes = None
    if is_multipart and "pdf_report" in request.files:
        file = request.files["pdf_report"]
        if file and file.filename:
            pdf_report_bytes = file.read()

    required = [name, age, gender, affected_side, affected_date, height, weight, bmi, leg_length, thigh_length, circumfrence_thigh, posterior_st, posterior_gracilis, lateral_st, lateral_gracilis]
    if not all(required):
        return jsonify({"error": "Missing required fields"}), 400

    if affected_side not in ["left knee", "right knee"]:
        return jsonify({"error": "affected_side must be 'left knee' or 'right knee'"}), 400

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor()

    insert_sql = (
        """
        INSERT INTO app_report (
            user_id, email, Name, Age, Gender, affected_side, affected_date, height, weight, bmi,
            leg_length, thigh_length, circumfrence_thigh,
            posterior_st, posterior_gracilis, lateral_st, lateral_gracilis,
            graft_diameter_1, graft_diameter_2, hamstring_autograft,
            quadriceps_tendon_diameter, minimum_st_length, predicted_st_value,
            gracilis_length, pdf_report
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s
        )
        """
    )

    cursor.execute(
        insert_sql,
        (
            user_id,
            email_from_token,
            name,
            age,
            gender,
            affected_side,
            affected_date,
            height,
            weight,
            bmi,
            leg_length,
            thigh_length,
            circumfrence_thigh,
            posterior_st,
            posterior_gracilis,
            lateral_st,
            lateral_gracilis,
            graft_diameter_1,
            graft_diameter_2,
            hamstring_autograft,
            quadriceps_tendon_diameter,
            minimum_st_length,
            predicted_st_value,
            gracilis_length,
            pdf_report_bytes,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    # If a PDF was uploaded, also save to filesystem and attempt to update a pdf_path column
    # refactor-note: PDFs are now persisted to storage.save_pdf() to avoid large BLOBs in DB.
    if pdf_report_bytes:
        try:
            saved_path = storage.save_pdf(new_id, pdf_report_bytes)
            try:
                ucur = conn.cursor()
                # Best-effort: update pdf_path column if it exists in schema
                ucur.execute("UPDATE app_report SET pdf_path = %s WHERE report_id = %s", (saved_path, new_id))
                conn.commit()
                ucur.close()
            except Exception:
                # If schema doesn't have pdf_path, ignore but keep file saved
                pass
        except Exception:
            logger.exception("Failed to persist uploaded PDF for report %s", new_id)
    cursor.close()
    conn.close()

    return jsonify({"message": "Report created", "report_id": new_id}), 201


@app.route("/reports", methods=["GET"])
def list_reports():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT report_id, user_id, email, Name, Age, Gender, affected_side, affected_date,
               height, weight, bmi, leg_length, thigh_length, circumfrence_thigh,
               posterior_st, posterior_gracilis, lateral_st, lateral_gracilis,
               submission_time,
               graft_diameter_1, graft_diameter_2, hamstring_autograft,
               quadriceps_tendon_diameter, minimum_st_length, predicted_st_value,
               gracilis_length
        FROM app_report
        WHERE user_id = %s
        ORDER BY submission_time DESC, report_id DESC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        if isinstance(row.get("affected_date"), datetime.date):
            row["affected_date"] = row["affected_date"].strftime("%Y-%m-%d")
        if isinstance(row.get("submission_time"), datetime.datetime):
            row["submission_time"] = row["submission_time"].strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({"reports": rows}), 200

# -------- NEW ENDPOINT: GET ALL REPORTS FROM ALL USERS --------
@app.route("/all_reports", methods=["GET"])
@auth.require_auth(role=["admin", "doctor"])
def get_all_reports():
    """Get all reports from all users in the app_report table (admin only)

    # refactor-note: protected with `require_auth(role='admin')` to enforce admin-only access.
    """

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT report_id, user_id, email, Name, Age, Gender, affected_side, affected_date,
               height, weight, bmi, leg_length, thigh_length, circumfrence_thigh,
               posterior_st, posterior_gracilis, lateral_st, lateral_gracilis,
               submission_time,
               graft_diameter_1, graft_diameter_2, hamstring_autograft,
               quadriceps_tendon_diameter, minimum_st_length, predicted_st_value,
               gracilis_length
        FROM app_report
        ORDER BY submission_time DESC, report_id DESC
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        if isinstance(row.get("affected_date"), datetime.date):
            row["affected_date"] = row["affected_date"].strftime("%Y-%m-%d")
        if isinstance(row.get("submission_time"), datetime.datetime):
            row["submission_time"] = row["submission_time"].strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({"reports": rows}), 200


@app.route("/reports/recent", methods=["GET"])
def recent_reports():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_role = decoded.get("user")
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    # Only doctors or admins can fetch recent reports across users
    if user_role is None or user_role.lower() not in ("doctor", "admin"):
        return jsonify({"error": "Forbidden"}), 403

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT report_id, user_id, email, Name, Age, Gender, affected_side, affected_date,
               height, weight, bmi, leg_length, thigh_length, circumfrence_thigh,
               posterior_st, posterior_gracilis, lateral_st, lateral_gracilis,
               submission_time,
               graft_diameter_1, graft_diameter_2, hamstring_autograft,
               quadriceps_tendon_diameter, minimum_st_length, predicted_st_value,
               gracilis_length
        FROM app_report
        ORDER BY submission_time DESC, report_id DESC
        LIMIT 5
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        if isinstance(row.get("affected_date"), datetime.date):
            row["affected_date"] = row["affected_date"].strftime("%Y-%m-%d")
        if isinstance(row.get("submission_time"), datetime.datetime):
            row["submission_time"] = row["submission_time"].strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({"reports": rows}), 200


@app.route("/me", methods=["GET"])
def who_am_i():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        return jsonify({
            "user_id": decoded.get("user_id"),
            "email": decoded.get("email"),
            "user": decoded.get("user")
        }), 200
    except Exception:
        return jsonify({"error": "Invalid token"}), 401


@app.route("/reports/<int:report_id>", methods=["GET"])
def get_report(report_id: int):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))
        user_role = decoded.get("user")  # Get user role from token
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    # Connect and fetch the report by id
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT report_id, user_id, email, Name, Age, Gender, affected_side, affected_date,
               height, weight, bmi, leg_length, thigh_length, circumfrence_thigh,
               posterior_st, posterior_gracilis, lateral_st, lateral_gracilis,
               submission_time,
               graft_diameter_1, graft_diameter_2, hamstring_autograft,
               quadriceps_tendon_diameter, minimum_st_length, predicted_st_value,
               gracilis_length
        FROM app_report
        WHERE report_id = %s
        """,
        (report_id,),
    )
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Report not found"}), 404

    report_owner_id = row.get("user_id")
    user_email = decoded.get("email")

    # Authorization logic:
    # 1. Allow if user is the owner
    # 2. Allow if user is a doctor (user_role = "doctor")
    # 3. Allow if report was shared to user's email
    allowed = False
    
    if report_owner_id == user_id:
        allowed = True
    elif user_role and user_role.lower() == "doctor":
        allowed = True
    else:
        # Check if this report was shared to the authenticated user's email
        scursor = conn.cursor(dictionary=True)
        scursor.execute(
            "SELECT 1 FROM shared_report WHERE reort_no = %s AND LOWER(to_mail) = LOWER(%s) LIMIT 1",
            (report_id, user_email),
        )
        shared_row = scursor.fetchone()
        scursor.close()
        if shared_row:
            allowed = True

    if not allowed:
        cursor.close()
        conn.close()
        return jsonify({"error": "Not authorized to view this report"}), 403

    # Convert date/time fields to strings if needed and return
    if isinstance(row.get("affected_date"), datetime.date):
        row["affected_date"] = row["affected_date"].strftime("%Y-%m-%d")
    if isinstance(row.get("submission_time"), datetime.datetime):
        row["submission_time"] = row["submission_time"].strftime("%Y-%m-%d %H:%M:%S")

    cursor.close()
    conn.close()
    return jsonify({"report": row}), 200

@app.route("/reports/<int:report_id>", methods=["DELETE"])
def delete_report(report_id: int):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_id = int(decoded.get("user_id"))
        user_role = decoded.get("user")  # Get user role from token
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor()

    # If user is a doctor, they can delete any report
    # Otherwise, only delete if they own the report
    if user_role and user_role.lower() == "doctor":
        cursor.execute("DELETE FROM app_report WHERE report_id = %s", (report_id,))
    else:
        cursor.execute("DELETE FROM app_report WHERE report_id = %s AND user_id = %s", (report_id, user_id))
    
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()

    if affected == 0:
        return jsonify({"error": "Report not found"}), 404

    return jsonify({"message": "Report deleted"}), 200
def decode_token_with_fallback(token):
    """
    Try to decode token with current SECRET_KEY.
    If that fails, try with known alternative keys for backward compatibility.
    Returns decoded payload or raises exception.
    """
    # Use new centralized decoder which implements DEBUG-only fallbacks
    # refactor-note: moved fallback logic into `auth.decode_token` and restricted to DEBUG mode
    return auth.decode_token(token)


@app.route("/share_report", methods=["POST"])
@auth.require_auth()
def share_report():
    """
    Share a report with another user.
    
    Request body:
    {
        "from_user_id": <current user's 11-digit ID>,
        "to_user_id": <recipient's 11-digit ID>,
        "report_id": <report ID to share>
    }
    
    Token is required. User authentication is done via JWT and `from_user_id` must match
    the authenticated user or the authenticated user must be admin.
    """
    data = request.json or {}
    from_user_id = data.get("from_user_id")
    to_user_id = data.get("to_user_id")
    report_id = data.get("report_id")

    # Validate required fields
    if not from_user_id or not to_user_id or not report_id:
        return jsonify({"error": "from_user_id, to_user_id, and report_id are required"}), 400
    # Authorization: ensure the token owner matches from_user_id or is admin
    # refactor-note: share_report now enforces token ownership to prevent unauthorized sharing
    current = getattr(g, 'current_user', None)
    if not current:
        return jsonify({"error": "Token missing or invalid"}), 401
    try:
        token_user_id = int(current.get("user_id"))
    except Exception:
        token_user_id = None
    if token_user_id != int(from_user_id) and (current.get("user") or "").lower() != "admin":
        return jsonify({"error": "Forbidden"}), 403

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Lookup sender email by from_user_id
    cursor.execute("SELECT email FROM signin WHERE id = %s", (from_user_id,))
    from_row = cursor.fetchone()
    if not from_row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Sender user id not found"}), 404

    from_mail = from_row.get("email")

    # Lookup recipient email by to_user_id
    cursor.execute("SELECT email FROM signin WHERE id = %s", (to_user_id,))
    to_row = cursor.fetchone()
    if not to_row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Recipient user id not found"}), 404

    to_mail = to_row.get("email")

    # Check 1: Prevent self-sharing (from_mail == to_mail)
    if from_mail.lower() == to_mail.lower():
        cursor.close()
        conn.close()
        return jsonify({"error": "Cannot share report with yourself"}), 400

    # Check 2: Prevent duplicate sharing (same report_id and to_mail already exist)
    cursor.execute(
        "SELECT sno FROM shared_report WHERE reort_no = %s AND LOWER(to_mail) = LOWER(%s) LIMIT 1",
        (report_id, to_mail)
    )
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Report already shared with this user"}), 400

    # Insert into shared_report table
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO shared_report (from_mail, to_mail, Date, reort_no) VALUES (%s, %s, %s, %s)",
            (from_mail, to_mail, datetime.date.today(), report_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to share report: " + str(e)}), 500

    cursor.close()
    conn.close()

    return jsonify({"message": "Report shared successfully"}), 201


@app.route("/share_report/<int:report_id>/<int:from_user_id>", methods=["GET"])
def get_shared_users_for_report(report_id: int, from_user_id: int):
    """
    Get all users that a report has been shared with by a specific user.
    
    Returns list of users with their details (id, first_name, last_name, email, user role, sno)
    """
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="graftpredict"
        )
        cursor = conn.cursor(dictionary=True)

        # Get sender's email from from_user_id
        cursor.execute("SELECT email FROM signin WHERE id = %s", (from_user_id,))
        sender_row = cursor.fetchone()
        if not sender_row:
            cursor.close()
            conn.close()
            return jsonify({"error": "User not found"}), 404

        sender_email = sender_row.get("email")

        # Get all shared_report records for this report, shared by this user
        cursor.execute(
            """
            SELECT sr.sno, sr.to_mail
            FROM shared_report sr
            WHERE sr.reort_no = %s AND LOWER(sr.from_mail) = LOWER(%s)
            """,
            (report_id, sender_email)
        )
        shared_rows = cursor.fetchall()

        # For each to_mail, lookup the user details from signin table
        shared_users = []
        for row in shared_rows:
            to_mail = row.get("to_mail")
            sno = row.get("sno")
            cursor.execute(
                "SELECT id, first_name, last_name, email, user FROM signin WHERE LOWER(email) = LOWER(%s)",
                (to_mail,)
            )
            user = cursor.fetchone()
            if user:
                shared_users.append({
                    "sno": sno,
                    "id": user.get("id"),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "email": user.get("email"),
                    "user": user.get("user")
                })

        cursor.close()
        conn.close()

        return jsonify({"shared_users": shared_users}), 200
    except Exception as e:
        print(f"Error fetching shared users: {e}")
        return jsonify({"error": "Server error"}), 500


@app.route("/shared_reports", methods=["GET"])
def get_shared_reports():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_email = decoded.get("email")
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Use case-insensitive match to ensure all rows for this email are returned
    cursor.execute(
        """
        SELECT sr.sno, sr.from_mail, sr.to_mail, sr.Date, sr.reort_no,
             s.id AS from_user_id,
             CONCAT(s.first_name, ' ', s.last_name) AS from_name,
             s.user AS from_user_role
        FROM shared_report sr
        LEFT JOIN signin s ON LOWER(s.email) = LOWER(sr.from_mail)
        WHERE LOWER(sr.to_mail) = LOWER(%s)
        ORDER BY sr.Date DESC, sr.sno DESC
        """,
        (user_email,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert Date objects to ISO strings
    for row in rows:
        if isinstance(row.get("Date"), datetime.date):
            row["Date"] = row["Date"].strftime("%Y-%m-%d")

    return jsonify({"shared_reports": rows}), 200


@app.route("/shared_reports/sent", methods=["GET"])
def get_sent_shared_reports():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_email = decoded.get("email")
        if not user_email:
            return jsonify({"error": "Email not found in token"}), 401
        print(f"[DEBUG] /shared_reports/sent - Token decoded, user_email: {user_email}")
    except Exception as e:
        print(f"[ERROR] Token decoding failed: {str(e)}")
        return jsonify({"error": "Invalid token"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT sr.sno, sr.from_mail, sr.to_mail, sr.Date, sr.reort_no,
               s.id AS to_user_id,
               CONCAT(s.first_name, ' ', s.last_name) AS to_name,
               s.user AS to_user_role
        FROM shared_report sr
        LEFT JOIN signin s ON LOWER(s.email) = LOWER(sr.to_mail)
        WHERE LOWER(sr.from_mail) = LOWER(%s)
        ORDER BY sr.Date DESC, sr.sno DESC
        """,
        (user_email,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"[DEBUG] /shared_reports/sent - Found {len(rows)} reports for {user_email}")

    # Convert Date objects to ISO strings
    for row in rows:
        if isinstance(row.get("Date"), datetime.date):
            row["Date"] = row["Date"].strftime("%Y-%m-%d")

    return jsonify({"shared_reports": rows}), 200


@app.route("/shared_reports/<int:sno>", methods=["DELETE"])
def delete_shared_report(sno: int):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_email = decoded.get("email")
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Ensure the share entry exists and belongs to this user (either to_mail OR from_mail)
    cursor.execute("SELECT to_mail, from_mail FROM shared_report WHERE sno = %s", (sno,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Shared report not found"}), 404

    # Allow deletion if the current user is either the recipient (to_mail) or the sender (from_mail)
    to_mail = row.get("to_mail") or ""
    from_mail = row.get("from_mail") or ""
    if (to_mail.lower() != (user_email or "").lower()) and (from_mail.lower() != (user_email or "").lower()):
        cursor.close()
        conn.close()
        return jsonify({"error": "Not authorized to delete this shared report"}), 403

    # Delete the shared_report row
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shared_report WHERE sno = %s", (sno,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to delete shared report: " + str(e)}), 500

    cursor.close()
    conn.close()
    return jsonify({"message": "Shared report deleted"}), 200


# ---------------- ADMIN: LIST DOCTORS ----------------
@app.route("/admin/doctors", methods=["GET"])
def list_doctors():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401
    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_role = decoded.get("user")
        if user_role is None or user_role.lower() != "admin":
            return jsonify({"error": "Forbidden"}), 403
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, first_name, last_name, email, created_at FROM signin WHERE `user` = %s", ("doctor",))
    rows = cursor.fetchall()

    # Convert datetime to string for JSON and fetch user_details
    doctors = []
    for r in rows:
        created = r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("created_at") else None
        
        # Fetch user_details for this doctor
        cursor.execute("SELECT dob, gender, age FROM user_details WHERE user_id = %s", (r["id"],))
        details = cursor.fetchone()
        
        doctor_data = {
            "id": r["id"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "email": r["email"],
            "created_at": created,
            "dob": details.get("dob") if details else None,
            "gender": details.get("gender") if details else None,
            "age": details.get("age") if details else None
        }
        doctors.append(doctor_data)

    cursor.close()
    conn.close()

    return jsonify({"doctors": doctors}), 200

# ---------------- ADMIN: CREATE DOCTOR (admin only) ----------------
@app.route("/admin/create-doctor", methods=["POST"])
def admin_create_doctor():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401
    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_role = decoded.get("user")
        if user_role is None or user_role.lower() != "admin":
            return jsonify({"error": "Forbidden"}), 403
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    data = request.json or {}
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    email = data.get("email")
    password = data.get("password")
    dob = data.get("dob")  # Date of birth
    gender = data.get("gender")  # Gender
    user_role = data.get("user", "doctor")

    if not all([first_name, last_name, email, password]):
        return jsonify({"error": "All fields are required"}), 400

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Check if email exists (but allow emails with RESTRICTED suffix to be overwritten)
    check_email = email if not email.endswith("RESTRICTED") else email[:-10]
    cursor.execute("SELECT * FROM signin WHERE email = %s OR email = %s", (email, check_email + "RESTRICTED"))
    if cursor.fetchone() and not email.endswith("RESTRICTED"):
        cursor.close()
        conn.close()
        return jsonify({"error": "Email already exists"}), 400

    # Generate unique 11-digit user ID
    try:
        user_id = generate_unique_user_id(cursor)
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to generate user ID. Please try again."}), 500

    # Hash password  
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode('utf-8')

    # Insert into DB with explicit ID, user role and auth_provider
    try:
        cursor.execute(
            "INSERT INTO signin (id, first_name, last_name, email, password_hash, `user`, auth_provider) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, first_name, last_name, email, hashed_password, user_role, 'local')
        )
    except Exception:
        # Fallback for databases that don't yet have auth_provider column
        cursor.execute(
            "INSERT INTO signin (id, first_name, last_name, email, password_hash, `user`) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, first_name, last_name, email, hashed_password, user_role)
        )
    conn.commit()

    # Insert user details with dob, gender, calculated age, and default language
    try:
        age = None
        if dob:
            # Calculate age from date of birth
            dob_date = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
            today = datetime.datetime.now().date()
            age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
        
        # Insert into user_details table with dob, gender, age, and default language "English"
        cursor.execute("""
            INSERT INTO user_details (user_id, dob, gender, age, language)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, dob, gender, age, "English"))
        conn.commit()
    except Exception as e:
        print(f"Warning: Failed to insert user details: {e}")
        # Don't fail the doctor creation if user_details insertion fails
        pass
    
    cursor.close()
    conn.close()

    return jsonify({"message": "Doctor created successfully", "user_id": user_id}), 201

# ---------------- ADMIN: RESTRICT DOCTOR ACCOUNT ----------------
@app.route("/admin/doctor/restrict", methods=["POST"])
def restrict_doctor():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401
    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_role = decoded.get("user")
        if user_role is None or user_role.lower() != "admin":
            return jsonify({"error": "Forbidden"}), 403
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    data = request.json or {}
    doctor_id = data.get("doctor_id")
    
    if not doctor_id:
        return jsonify({"error": "Doctor ID is required"}), 400

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Get current email
    cursor.execute("SELECT email FROM signin WHERE id = %s", (doctor_id,))
    doctor = cursor.fetchone()
    
    if not doctor:
        cursor.close()
        conn.close()
        return jsonify({"error": "Doctor not found"}), 404

    email = doctor["email"]
    
    # Add RESTRICTED suffix if not already present
    if not email.endswith("RESTRICTED"):
        new_email = email + "RESTRICTED"
        cursor.execute("UPDATE signin SET email = %s WHERE id = %s", (new_email, doctor_id))
        conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Doctor account restricted"}), 200

# ---------------- ADMIN: ACTIVATE DOCTOR ACCOUNT ----------------
@app.route("/admin/doctor/activate", methods=["POST"])
def activate_doctor():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401
    try:
        token = auth_header.split(" ")[1]
        decoded = decode_token_with_fallback(token)
        user_role = decoded.get("user")
        if user_role is None or user_role.lower() != "admin":
            return jsonify({"error": "Forbidden"}), 403
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    data = request.json or {}
    doctor_id = data.get("doctor_id")
    
    if not doctor_id:
        return jsonify({"error": "Doctor ID is required"}), 400

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    # Get current email
    cursor.execute("SELECT email FROM signin WHERE id = %s", (doctor_id,))
    doctor = cursor.fetchone()
    
    if not doctor:
        cursor.close()
        conn.close()
        return jsonify({"error": "Doctor not found"}), 404

    email = doctor["email"]
    
    # Remove RESTRICTED suffix if present
    if email.endswith("RESTRICTED"):
        new_email = email[:-10]  # Remove last 10 characters ("RESTRICTED")
        cursor.execute("UPDATE signin SET email = %s WHERE id = %s", (new_email, doctor_id))
        conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Doctor account activated"}), 200

# ---------------- ADMIN: CHECK IF ADMIN EXISTS ----------------
@app.route("/admin/exists", methods=["GET"])
def admin_exists():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as cnt FROM signin WHERE LOWER(`user`) = 'admin'")
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    exists = False
    if row and row.get("cnt") is not None:
        exists = row.get("cnt") > 0

    return jsonify({"exists": exists}), 200


# DIAGNOSTIC ENDPOINT - Remove in production
@app.route("/debug/secret-key", methods=["GET"])
def debug_secret_key():
    """Diagnostic endpoint to check current SECRET_KEY state (DEBUG ONLY)"""
    if not DEBUG:
        return jsonify({"error": "Not available in production"}), 403
    env_secret = os.environ.get("SECRET_KEY", "NOT SET")
    # Avoid exposing full secrets; only show preview in DEBUG.
    sk = config.SECRET_KEY
    return jsonify({
        "debug_mode": DEBUG,
        "secret_key_set": sk is not None,
        "secret_key_preview": (str(sk)[:20] + "...") if sk else "None",
        "env_secret_key_set": env_secret != "NOT SET",
        "env_secret_key_preview": (env_secret[:20] + "...") if env_secret != "NOT SET" else "NOT SET"
    }), 200


# ---------------- FORGOT PASSWORD: helpers and endpoints ----------------
def generate_otp():
    """Generate a zero-padded 6-digit OTP as string"""
    return f"{random.randint(0, 999999):06d}"


def send_otp_email(recipient_email, otp):
    """Send the OTP via Flask-Mail. Returns (True, None) on success or (False, error_message) on failure."""
    # Ensure we're in app context (needed for background threads)
    with app.app_context():
        if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
            return False, "Mail server not configured"

        try:
            msg = Message(
                subject="GraftPredict Password Reset OTP",
                recipients=[recipient_email],
            )
            msg.body = (
                f"Your One-Time Password (OTP) for password reset is: {otp}\n"
                "This OTP is valid for 5 minutes. If you did not request this, please ignore this email."
            )
            mail.send(msg)
            return True, None
        except Exception as e:
            app.logger.exception("Failed to send OTP email")
            return False, str(e)


@app.route("/forgot-password/send-otp", methods=["POST"])
@limiter.limit("3 per minute")
def forgot_password_send_otp():
    data = request.json or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Verify email exists but do not reveal existence in response
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM signin WHERE LOWER(email) = LOWER(%s) LIMIT 1", (email,))
    user = cursor.fetchone()
    user_exists = bool(user)

    # Check resend cooldown: if an OTP was generated less than 60 seconds ago, refuse and return retry_after
    try:
        ccheck = conn.cursor(dictionary=True)
        ccheck.execute("SELECT otp, expiry FROM password_reset WHERE email = %s", (email,))
        existing = ccheck.fetchone()
        ccheck.close()
        if existing and existing.get("expiry"):
            existing_expiry = existing.get("expiry")
            # treat DB-stored datetime as UTC naive
            if getattr(existing_expiry, 'tzinfo', None) is None:
                existing_expiry = existing_expiry.replace(tzinfo=datetime.timezone.utc)
            generation_time = existing_expiry - datetime.timedelta(minutes=5)
            now = datetime.datetime.now(datetime.timezone.utc)
            seconds_since = (now - generation_time).total_seconds()
            if seconds_since < 60:
                retry_after = int(60 - seconds_since)
                cursor.close()
                conn.close()
                return jsonify({"error": "Please wait before requesting a new OTP", "retry_after": retry_after}), 429
    except Exception:
        # Non-fatal: if check fails just proceed to generate OTP
        pass

    otp = generate_otp()
    # Use timezone-aware UTC datetime
    expiry_aware = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    expiry_db = expiry_aware.replace(tzinfo=None)

    if user_exists:
        try:
            # Use REPLACE to insert or update existing OTP row
            cursor = conn.cursor()
            cursor.execute(
                "REPLACE INTO password_reset (email, otp, expiry) VALUES (%s, %s, %s)",
                (email, otp, expiry_db)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({"error": "Failed to store OTP"}), 500

        # Send email asynchronously so request returns quickly
        try:
            import threading
            threading.Thread(target=send_otp_email, args=(email, otp), daemon=True).start()
        except Exception:
            logger.exception("Failed to start background email thread")

    # Close DB and always return a neutral message to prevent user enumeration
    cursor.close()
    conn.close()
    if DEBUG_SHOW_OTP:
        return jsonify({"message": "If an account exists, an OTP was sent. Retry after 60 seconds.", "otp": otp, "retry_after": 60}), 200
    return jsonify({"message": "If an account exists, an OTP was sent. Retry after 60 seconds.", "retry_after": 60}), 200



@app.route("/signup/send-otp", methods=["POST"])
@limiter.limit("3 per minute")
def signup_send_otp():
    data = request.json or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Do NOT require email to exist; this is for verifying email ownership during signup
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )

    # Check resend cooldown
    try:
        ccheck = conn.cursor(dictionary=True)
        ccheck.execute("SELECT otp, expiry FROM password_reset WHERE email = %s", (email,))
        existing = ccheck.fetchone()
        ccheck.close()
        if existing and existing.get("expiry"):
            existing_expiry = existing.get("expiry")
            if getattr(existing_expiry, 'tzinfo', None) is None:
                existing_expiry = existing_expiry.replace(tzinfo=datetime.timezone.utc)
            generation_time = existing_expiry - datetime.timedelta(minutes=5)
            now = datetime.datetime.now(datetime.timezone.utc)
            seconds_since = (now - generation_time).total_seconds()
            if seconds_since < 60:
                retry_after = int(60 - seconds_since)
                return jsonify({"error": "Please wait before requesting a new OTP", "retry_after": retry_after}), 429
    except Exception:
        pass

    otp = generate_otp()
    expiry_aware = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    expiry_db = expiry_aware.replace(tzinfo=None)

    try:
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO password_reset (email, otp, expiry) VALUES (%s, %s, %s)",
            (email, otp, expiry_db)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to store OTP"}), 500

    # Send asynchronously and return a neutral response
    try:
        import threading
        threading.Thread(target=send_otp_email, args=(email, otp), daemon=True).start()
    except Exception:
        logger.exception("Failed to start background email thread")

    cursor.close()
    conn.close()
    if DEBUG_SHOW_OTP:
        return jsonify({"message": "OTP sent to email", "otp": otp, "retry_after": 60}), 200
    return jsonify({"message": "OTP sent to email", "retry_after": 60}), 200


@app.route("/forgot-password/verify-otp", methods=["POST"])
def forgot_password_verify_otp():
    data = request.json or {}
    email = data.get("email")
    otp = data.get("otp")
    if not email or not otp:
        return jsonify({"error": "Email and otp are required"}), 400

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="graftpredict"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT otp, expiry FROM password_reset WHERE email = %s", (email,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "No OTP found for this email"}), 404

    db_otp = row.get("otp")
    expiry = row.get("expiry")

    if not db_otp or not expiry:
        cursor.close()
        conn.close()
        return jsonify({"error": "Invalid OTP record"}), 400

    # Treat DB-stored datetime as UTC naive and compare with timezone-aware now
    if getattr(expiry, 'tzinfo', None) is None:
        expiry = expiry.replace(tzinfo=datetime.timezone.utc)

    if datetime.datetime.now(datetime.timezone.utc) > expiry:
        cursor.close()
        conn.close()
        return jsonify({"error": "OTP has expired"}), 400

    if str(otp) != str(db_otp):
        cursor.close()
        conn.close()
        return jsonify({"error": "OTP is incorrect"}), 400

    cursor.close()
    conn.close()
    return jsonify({"message": "OTP verified"}), 200


@app.route("/forgot-password/reset-password", methods=["POST"])
def forgot_password_reset():
    data = request.json or {}
    email = data.get("email")
    new_password = data.get("new_password")

    if not email or not new_password:
        return jsonify({"error": "Email and new_password are required"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    conn = compat_connect()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM signin WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "No account found with this email"}), 404

    try:
        hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode('utf-8')
        ucursor = conn.cursor()
        ucursor.execute("UPDATE signin SET password_hash = %s WHERE LOWER(email) = LOWER(%s)", (hashed_password, email.strip()))
        conn.commit()
        ucursor.close()
        cursor.close()
        conn.close()
        return jsonify({"message": "Password updated successfully"}), 200
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({"error": f"Failed to update password: {str(e)}"}), 500

@app.route("/change-password", methods=["POST"])
def change_password():
    """Change password for authenticated user"""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))
        email = decoded.get("email")
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    # Get request data
    data = request.get_json()
    old_password = data.get("old_password", "").strip()
    new_password = data.get("new_password", "").strip()

    # Validate input
    if not old_password or not new_password:
        return jsonify({"error": "Old password and new password are required"}), 400

    # Validate new password rules
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    if not any(c.isupper() for c in new_password):
        return jsonify({"error": "New password must contain at least 1 uppercase letter"}), 400
    if not any(c.islower() for c in new_password):
        return jsonify({"error": "New password must contain at least 1 lowercase letter"}), 400
    if not any(c.isdigit() for c in new_password):
        return jsonify({"error": "New password must contain at least 1 digit"}), 400
    if not any(c in "!@#$%^&*" for c in new_password):
        return jsonify({"error": "New password must contain at least 1 special character (!@#$%^&*)"}), 400

    # Check if new password is same as old password
    if old_password == new_password:
        return jsonify({"error": "New password must be different from current password"}), 400

    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="graftpredict"
        )
        cursor = conn.cursor(dictionary=True)

        # Get current password hash
        cursor.execute("SELECT password_hash FROM signin WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            return jsonify({"error": "User not found"}), 404

        # Verify old password
        if not bcrypt.checkpw(old_password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            cursor.close()
            conn.close()
            return jsonify({"error": "Current password is incorrect"}), 401

        # Hash new password
        hashed_new_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode('utf-8')

        # Update password
        cursor.execute("UPDATE signin SET password_hash = %s WHERE id = %s", 
                      (hashed_new_password, user_id))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        print(f"[ERROR] Error changing password: {str(e)}")
        return jsonify({"error": "Failed to change password"}), 500


@app.route("/delete-account", methods=["DELETE"])
def delete_account():
    """Delete user account and all associated data"""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded = auth.decode_token(token)
        user_id = int(decoded.get("user_id"))
        email = decoded.get("email")
    except Exception:
        return jsonify({"error": "Invalid token"}), 401

    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="graftpredict"
        )
        cursor = conn.cursor()

        # Delete in order of foreign key dependencies
        # 1. Delete from shared_report (uses email addresses: from_mail and to_mail)
        cursor.execute("DELETE FROM shared_report WHERE LOWER(from_mail) = LOWER(%s) OR LOWER(to_mail) = LOWER(%s)", 
                      (email, email))
        
        # 2. Delete from app_report (depends on user)
        cursor.execute("DELETE FROM app_report WHERE user_id = %s", (user_id,))
        
        # 3. Delete from user_details (depends on user)
        cursor.execute("DELETE FROM user_details WHERE user_id = %s", (user_id,))
        
        # 4. Delete from password_reset (depends on email)
        cursor.execute("DELETE FROM password_reset WHERE email = %s", (email,))
        
        # 5. Delete from signin (primary user record)
        cursor.execute("DELETE FROM signin WHERE id = %s", (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Account deleted successfully"}), 200

    except Exception as e:
        print(f"[ERROR] Error deleting account: {str(e)}")
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return jsonify({"error": "Failed to delete account"}), 500


# Health endpoints
@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


@app.route("/readyz", methods=["GET"])
def readyz():
    # Basic readiness check: attempt to get a pooled DB connection
    try:
        conn = mysql.connector.connect()
        conn.close()
        return jsonify({"ready": True}), 200
    except Exception:
        return jsonify({"ready": False}), 500


if __name__ == "__main__":
    # Local development server. In production, use a WSGI server (e.g. gunicorn).
    # Respect DEBUG env variable (only enable Flask debug when explicitly requested).
    if DEBUG:
        app.logger.info("Starting development server on %s:%s (DEBUG=%s)", HOST, PORT, DEBUG)
        app.run(host=HOST, port=PORT, debug=True)
    else:
        app.logger.info("Starting server on %s:%s (production mode). Use a WSGI server like gunicorn.", HOST, PORT)
        app.run(host=HOST, port=PORT, debug=False)


@app.errorhandler(500)
def handle_500(e):
    logger.exception("Unhandled exception: %s", e)
    return jsonify({"error": "Internal server error"}), 500
