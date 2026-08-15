"""
Personal Finance Tracker with Expense Analytics
Flask + SQLAlchemy (SQLite) + Chart.js
"""
import os
from datetime import datetime, date
from collections import defaultdict

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'finance.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# ---------------- Models ----------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    monthly_budget = db.Column(db.Float, default=0.0)
    transactions = db.relationship("Transaction", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    category = db.Column(db.String(50), nullable=False)
    note = db.Column(db.String(255))
    txn_date = db.Column(db.Date, nullable=False, default=date.today)
    is_recurring = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


DEFAULT_CATEGORIES = [
    "Food", "Transport", "Rent", "Utilities", "Entertainment",
    "Shopping", "Health", "Education", "Salary", "Other",
]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------- Auth Routes ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already registered.", "error")
            return redirect(url_for("register"))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------- Core App Routes ----------------

@app.route("/")
@login_required
def dashboard():
    return render_template(
        "index.html",
        username=current_user.username,
        categories=DEFAULT_CATEGORIES,
        budget=current_user.monthly_budget,
    )


@app.route("/api/transactions", methods=["GET", "POST"])
@login_required
def api_transactions():
    if request.method == "POST":
        data = request.get_json()
        try:
            txn = Transaction(
                user_id=current_user.id,
                amount=float(data["amount"]),
                type=data["type"],
                category=data.get("category") or "Other",
                note=data.get("note", ""),
                txn_date=datetime.strptime(data["date"], "%Y-%m-%d").date(),
                is_recurring=bool(data.get("is_recurring", False)),
            )
        except (KeyError, ValueError) as e:
            return jsonify({"error": f"Invalid input: {e}"}), 400

        db.session.add(txn)
        db.session.commit()
        return jsonify({"message": "Transaction added", "id": txn.id}), 201

    # GET — list, newest first
    txns = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
        .all()
    )
    return jsonify([
        {
            "id": t.id,
            "amount": t.amount,
            "type": t.type,
            "category": t.category,
            "note": t.note,
            "date": t.txn_date.isoformat(),
            "is_recurring": t.is_recurring,
        }
        for t in txns
    ])


@app.route("/api/transactions/<int:txn_id>", methods=["DELETE"])
@login_required
def delete_transaction(txn_id):
    txn = Transaction.query.filter_by(id=txn_id, user_id=current_user.id).first()
    if not txn:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(txn)
    db.session.commit()
    return jsonify({"message": "Deleted"})


@app.route("/api/budget", methods=["POST"])
@login_required
def set_budget():
    data = request.get_json()
    try:
        current_user.monthly_budget = float(data["budget"])
        db.session.commit()
        return jsonify({"message": "Budget updated", "budget": current_user.monthly_budget})
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid budget value"}), 400


@app.route("/api/analytics/summary")
@login_required
def analytics_summary():
    """Category breakdown + monthly income/expense totals + simple forecast."""
    txns = Transaction.query.filter_by(user_id=current_user.id).all()

    category_totals = defaultdict(float)
    monthly_totals = defaultdict(lambda: {"income": 0.0, "expense": 0.0})

    for t in txns:
        if t.type == "expense":
            category_totals[t.category] += t.amount
        month_key = t.txn_date.strftime("%Y-%m")
        monthly_totals[month_key][t.type] += t.amount

    sorted_months = sorted(monthly_totals.keys())
    monthly_expense_series = [monthly_totals[m]["expense"] for m in sorted_months]

    # Simple 3-month moving average forecast for next month's spending
    forecast = None
    if len(monthly_expense_series) >= 1:
        window = monthly_expense_series[-3:]
        forecast = round(sum(window) / len(window), 2)

    total_income = sum(v["income"] for v in monthly_totals.values())
    total_expense = sum(v["expense"] for v in monthly_totals.values())

    current_month = date.today().strftime("%Y-%m")
    current_month_expense = monthly_totals.get(current_month, {"expense": 0.0})["expense"]
    budget = current_user.monthly_budget
    budget_alert = None
    if budget and current_month_expense > 0:
        pct = (current_month_expense / budget) * 100 if budget else 0
        if pct >= 100:
            budget_alert = {"level": "danger", "message": f"You've exceeded your monthly budget ({pct:.0f}% used)."}
        elif pct >= 80:
            budget_alert = {"level": "warning", "message": f"You've used {pct:.0f}% of your monthly budget."}

    return jsonify({
        "category_totals": category_totals,
        "months": sorted_months,
        "monthly_income": [monthly_totals[m]["income"] for m in sorted_months],
        "monthly_expense": monthly_expense_series,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_savings": total_income - total_expense,
        "forecast_next_month": forecast,
        "current_month_expense": current_month_expense,
        "budget": budget,
        "budget_alert": budget_alert,
    })


def create_db():
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    create_db()
    app.run(debug=True, port=5000)
