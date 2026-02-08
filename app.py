from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
import jwt
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# Configure Flask to find templates in Frontend folder
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "Frontend"),
    static_folder=os.path.join(os.path.dirname(__file__), "Frontend"),
    static_url_path="/static",
)
CORS(app)

# Secret key for JWT
SECRET_KEY = "your-secret-key-change-this-in-production"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medicine_expiry.db")


def init_db():
    """Initialize database with users and medicines tables"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create medicines table with user_id
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            batch TEXT NOT NULL,
            expiry TEXT NOT NULL,
            barcode TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


# Initialize database on startup
init_db()


def get_db():
    return sqlite3.connect(DB_PATH)


# JWT Token decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_id = data["user_id"]
        except:
            return jsonify({"error": "Invalid token"}), 401

        return f(current_user_id, *args, **kwargs)

    return decorated


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400

        hashed_password = generate_password_hash(password)
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, hashed_password),
            )
            conn.commit()
            conn.close()
            return jsonify({"message": "User created successfully"}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"error": "Email already exists"}), 400

    except Exception as e:
        return jsonify({"error": f"Signup failed: {str(e)}"}), 500


@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if not user or not check_password_hash(user[1], password):
            return jsonify({"error": "Invalid email or password"}), 401

        token = jwt.encode({"user_id": user[0]}, SECRET_KEY, algorithm="HS256")

        return jsonify({"token": token}), 200

    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500


@app.route("/add", methods=["POST"])
@token_required
def add_medicine(current_user_id):
    try:
        data = request.json

        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["name", "batch", "expiry", "barcode", "quantity"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return jsonify(
                {"error": f"Missing fields: {', '.join(missing_fields)}"}
            ), 400

        try:
            quantity = int(data["quantity"])
            if quantity < 0:
                return jsonify({"error": "Quantity must be positive"}), 400
        except ValueError:
            return jsonify({"error": "Quantity must be a number"}), 400

        try:
            datetime.strptime(data["expiry"], "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Expiry date must be in YYYY-MM-DD format"}), 400

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO medicines (user_id, name, batch, expiry, barcode, quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                current_user_id,
                data["name"],
                data["batch"],
                data["expiry"],
                data["barcode"],
                quantity,
            ),
        )

        conn.commit()
        conn.close()
        return jsonify({"message": "Medicine added successfully"}), 201

    except Exception as e:
        return jsonify({"error": f"Failed to add medicine: {str(e)}"}), 500


@app.route("/medicines", methods=["GET"])
@token_required
def get_medicines(current_user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM medicines WHERE user_id = ?", (current_user_id,))
        rows = cur.fetchall()
        conn.close()

        medicines = []
        for r in rows:
            try:
                expiry = datetime.strptime(r[4], "%Y-%m-%d")
                days_left = (expiry - datetime.today()).days

                if days_left < 0:
                    status = "expired"
                elif days_left <= 30:
                    status = "warning"
                else:
                    status = "safe"

                medicines.append(
                    {
                        "id": r[0],
                        "name": r[2],
                        "batch": r[3],
                        "expiry": r[4],
                        "barcode": r[5],
                        "quantity": r[6],
                        "days_left": days_left,
                        "status": status,
                    }
                )
            except ValueError:
                continue

        return jsonify(medicines), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch medicines: {str(e)}"}), 500


@app.route("/delete/<int:id>", methods=["DELETE"])
@token_required
def delete_medicine(current_user_id, id):
    try:
        conn = get_db()
        cur = conn.cursor()
        # Ensure user can only delete their own medicines
        cur.execute(
            "DELETE FROM medicines WHERE id=? AND user_id=?", (id, current_user_id)
        )

        if cur.rowcount == 0:
            conn.close()
            return jsonify({"error": f"Medicine with id {id} not found"}), 404

        conn.commit()
        conn.close()
        return jsonify({"message": f"Medicine {id} deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to delete medicine: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1000, debug=False)
