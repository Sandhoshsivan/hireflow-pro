"""
HireFlow Pro — Production-Ready Enterprise Job Application Tracker
"""
import os
import re
import hashlib
import secrets
import logging
from datetime import datetime, date, timedelta, timezone
from functools import wraps

from flask import (Flask, jsonify, request, render_template, g, session,
                   redirect, url_for, Response)

# ── App Factory ───────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max request
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('hireflow')

# ── Database (PostgreSQL for production, SQLite for local dev) ────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL:
    # PostgreSQL (Render, Railway, etc.)
    import psycopg2
    import psycopg2.extras
    # Fix Render's postgres:// -> postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    def get_db():
        if 'db' not in g:
            g.db = psycopg2.connect(DATABASE_URL)
            g.db.autocommit = False
        return g.db

    def db_execute(sql, params=None):
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or ())
        return cur

    def db_fetchone(sql, params=None):
        cur = db_execute(sql, params)
        return cur.fetchone()

    def db_fetchall(sql, params=None):
        cur = db_execute(sql, params)
        return cur.fetchall()

    def db_commit():
        get_db().commit()

    def db_lastrowid(cur):
        return cur.fetchone()['id'] if cur.description else None

    IS_POSTGRES = True
else:
    # SQLite (local development)
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), 'hireflow.db')

    def get_db():
        if 'db' not in g:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA journal_mode=WAL")
            g.db.execute("PRAGMA foreign_keys=ON")
        return g.db

    def db_execute(sql, params=None):
        db = get_db()
        # Convert %s placeholders to ? for SQLite
        sql = sql.replace('%s', '?')
        return db.execute(sql, params or ())

    def db_fetchone(sql, params=None):
        cur = db_execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def db_fetchall(sql, params=None):
        cur = db_execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def db_commit():
        get_db().commit()

    def db_lastrowid(cur):
        return cur.lastrowid

    IS_POSTGRES = False

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()

# ── Plan Configuration ───────────────────────────────────────────────────────
PLANS = {
    'free': {
        'name': 'Free', 'price': 0, 'app_limit': 5,
        'ai_assistant': False, 'advanced_analytics': False,
        'csv_export': False, 'pipeline_view': False,
        'contacts': False, 'priority_support': False,
    },
    'pro': {
        'name': 'Pro', 'price': 9, 'app_limit': 999999,
        'ai_assistant': True, 'advanced_analytics': True,
        'csv_export': True, 'pipeline_view': True,
        'contacts': True, 'priority_support': False,
    },
    'premium': {
        'name': 'Premium', 'price': 19, 'app_limit': 999999,
        'ai_assistant': True, 'advanced_analytics': True,
        'csv_export': True, 'pipeline_view': True,
        'contacts': True, 'priority_support': True,
    },
}

# ── Database Init ─────────────────────────────────────────────────────────────
def init_db():
    if IS_POSTGRES:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                email       TEXT NOT NULL UNIQUE,
                password    TEXT NOT NULL,
                role_title  TEXT DEFAULT 'Job Seeker',
                plan        TEXT DEFAULT 'free',
                plan_started TIMESTAMPTZ,
                stripe_customer_id TEXT,
                is_admin    BOOLEAN DEFAULT FALSE,
                is_blocked  BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS applications (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL DEFAULT 0,
                company     TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'Applied',
                date_applied TEXT,
                salary      TEXT DEFAULT '',
                source      TEXT DEFAULT 'LinkedIn',
                location    TEXT DEFAULT '',
                followup    TEXT,
                priority    TEXT DEFAULT 'medium',
                job_url     TEXT DEFAULT '',
                notes       TEXT DEFAULT '',
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS timeline (
                id          SERIAL PRIMARY KEY,
                app_id      INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                action      TEXT NOT NULL,
                note        TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS contacts (
                id          SERIAL PRIMARY KEY,
                app_id      INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                name        TEXT,
                role        TEXT,
                email       TEXT,
                linkedin    TEXT,
                notes       TEXT
            );
            CREATE TABLE IF NOT EXISTS payments (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                plan        TEXT NOT NULL,
                amount      REAL NOT NULL,
                currency    TEXT DEFAULT 'USD',
                status      TEXT DEFAULT 'completed',
                stripe_session_id TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS password_resets (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                token       TEXT NOT NULL UNIQUE,
                expires_at  TIMESTAMPTZ NOT NULL,
                used        BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        conn.close()
        logger.info("PostgreSQL database initialized")
    else:
        import sqlite3
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                email       TEXT NOT NULL UNIQUE,
                password    TEXT NOT NULL,
                role_title  TEXT DEFAULT 'Job Seeker',
                plan        TEXT DEFAULT 'free',
                plan_started TEXT,
                stripe_customer_id TEXT,
                is_admin    INTEGER DEFAULT 0,
                is_blocked  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS applications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL DEFAULT 0,
                company     TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'Applied',
                date_applied TEXT,
                salary      TEXT DEFAULT '',
                source      TEXT DEFAULT 'LinkedIn',
                location    TEXT DEFAULT '',
                followup    TEXT,
                priority    TEXT DEFAULT 'medium',
                job_url     TEXT DEFAULT '',
                notes       TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS timeline (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id      INTEGER NOT NULL,
                action      TEXT NOT NULL,
                note        TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(app_id) REFERENCES applications(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS contacts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id      INTEGER NOT NULL,
                name        TEXT,
                role        TEXT,
                email       TEXT,
                linkedin    TEXT,
                notes       TEXT,
                FOREIGN KEY(app_id) REFERENCES applications(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS payments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                plan        TEXT NOT NULL,
                amount      REAL NOT NULL,
                currency    TEXT DEFAULT 'USD',
                status      TEXT DEFAULT 'completed',
                stripe_session_id TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS password_resets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                token       TEXT NOT NULL UNIQUE,
                expires_at  TEXT NOT NULL,
                used        INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)
        # Migrations for existing DBs
        for col, sql in [
            ('user_id', "ALTER TABLE applications ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"),
            ('plan', "ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'"),
            ('plan_started', "ALTER TABLE users ADD COLUMN plan_started TEXT"),
            ('stripe_customer_id', "ALTER TABLE users ADD COLUMN stripe_customer_id TEXT"),
            ('is_admin', "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0"),
            ('is_blocked', "ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0"),
        ]:
            try:
                table = 'applications' if col == 'user_id' else 'users'
                db.execute(f"SELECT {col} FROM {table} LIMIT 1")
            except sqlite3.OperationalError:
                db.execute(sql)
                db.commit()
        # Create password_resets table if not exists (already in executescript above)
        db.close()
        logger.info("SQLite database initialized")

# ── Security: Password Hashing ────────────────────────────────────────────────
def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
    return salt + ':' + h.hex()

def verify_password(stored, password):
    try:
        salt, h = stored.split(':')
        check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
        return secrets.compare_digest(check.hex(), h)
    except (ValueError, AttributeError):
        return False

# ── Rate Limiting (in-memory, simple) ─────────────────────────────────────────
_rate_limits = {}

def rate_limit(key, max_requests=10, window=60):
    """Simple in-memory rate limiter. Returns True if rate limited."""
    now = datetime.now().timestamp()
    if key not in _rate_limits:
        _rate_limits[key] = []
    # Clean old entries
    _rate_limits[key] = [t for t in _rate_limits[key] if t > now - window]
    if len(_rate_limits[key]) >= max_requests:
        return True
    _rate_limits[key].append(now)
    return False

# ── Auth Helpers ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Login required'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def current_user_id():
    return session.get('user_id')

def is_admin():
    return session.get('is_admin', False)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Login required'}), 401
            return redirect(url_for('login_page'))
        if not session.get('is_admin'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return decorated

def get_user_plan():
    plan_key = session.get('user_plan', 'free')
    return PLANS.get(plan_key, PLANS['free'])

def require_feature(feature):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('is_admin'):
                return f(*args, **kwargs)
            plan = get_user_plan()
            if not plan.get(feature, False):
                return jsonify({
                    'error': 'upgrade_required',
                    'message': f'This feature requires a Pro or Premium plan. You are on the {plan["name"]} plan.',
                    'feature': feature,
                    'current_plan': session.get('user_plan', 'free'),
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── SQL Helpers ───────────────────────────────────────────────────────────────
def now_sql():
    return "NOW()" if IS_POSTGRES else "datetime('now')"

def date_sql(field, days_offset):
    if IS_POSTGRES:
        return f"{field} >= NOW() - INTERVAL '{abs(days_offset)} days'"
    return f"{field} >= date('now','-{abs(days_offset)} days')"

def month_sql(field):
    if IS_POSTGRES:
        return f"TO_CHAR({field}, 'YYYY-MM')"
    return f"strftime('%Y-%m', {field})"

def date_only_sql(field):
    if IS_POSTGRES:
        return f"DATE({field})"
    return f"date({field})"

# ── Security Headers Middleware ───────────────────────────────────────────────
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ── Error Handlers ────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 error: {e}")
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('errors/500.html'), 500

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Too many requests. Please slow down.'}), 429

# ── Health Check ──────────────────────────────────────────────────────────────
@app.route('/health')
def health_check():
    try:
        db_fetchone("SELECT 1 AS ok")
        return jsonify({'status': 'healthy', 'database': 'connected', 'timestamp': datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

# ── Auth Pages ────────────────────────────────────────────────────────────────
@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('register.html')

@app.route('/forgot-password')
def forgot_password_page():
    return render_template('forgot_password.html')

@app.route('/reset-password')
def reset_password_page():
    token = request.args.get('token', '')
    if not token:
        return redirect('/forgot-password')
    return render_template('reset_password.html', token=token)

# ── Auth API ──────────────────────────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    d = request.get_json()
    name = (d.get('name') or '').strip()
    email = (d.get('email') or '').strip().lower()
    password = d.get('password') or ''
    role_title = (d.get('role_title') or 'Job Seeker').strip()

    # Rate limit
    ip = request.remote_addr or 'unknown'
    if rate_limit(f'register:{ip}', max_requests=5, window=300):
        return jsonify({'error': 'Too many registration attempts. Please wait 5 minutes.'}), 429

    # Validation
    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400
    if len(name) > 100:
        return jsonify({'error': 'Name is too long'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    if len(password) > 128:
        return jsonify({'error': 'Password is too long'}), 400
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({'error': 'Invalid email format'}), 400
    if len(email) > 255:
        return jsonify({'error': 'Email is too long'}), 400

    existing = db_fetchone("SELECT id FROM users WHERE email=%s", (email,))
    if existing:
        return jsonify({'error': 'An account with this email already exists'}), 409

    hashed = hash_password(password)
    user_count = db_fetchone("SELECT COUNT(*) as cnt FROM users")
    make_admin = (user_count['cnt'] == 0)

    if IS_POSTGRES:
        cur = db_execute(
            "INSERT INTO users (name, email, password, role_title, plan, is_admin) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (name, email, hashed, role_title, 'free', make_admin))
        user_id = cur.fetchone()['id']
    else:
        cur = db_execute(
            "INSERT INTO users (name, email, password, role_title, plan, is_admin) VALUES (%s,%s,%s,%s,%s,%s)",
            (name, email, hashed, role_title, 'free', 1 if make_admin else 0))
        user_id = db_lastrowid(cur)
    db_commit()

    session.permanent = True
    session['user_id'] = user_id
    session['user_name'] = name
    session['user_email'] = email
    session['user_role'] = role_title
    session['user_plan'] = 'free'
    session['is_admin'] = make_admin

    logger.info(f"New user registered: {email} (admin={make_admin})")
    return jsonify({'message': 'Registration successful', 'user': {
        'id': user_id, 'name': name, 'email': email, 'is_admin': make_admin
    }}), 201

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    d = request.get_json()
    email = (d.get('email') or '').strip().lower()
    password = d.get('password') or ''

    # Rate limit by IP
    ip = request.remote_addr or 'unknown'
    if rate_limit(f'login:{ip}', max_requests=10, window=300):
        return jsonify({'error': 'Too many login attempts. Please wait 5 minutes.'}), 429

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = db_fetchone("SELECT * FROM users WHERE email=%s", (email,))
    if not user or not verify_password(user['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401
    if user['is_blocked']:
        return jsonify({'error': 'Your account has been suspended. Contact support.'}), 403

    session.permanent = True
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']
    session['user_role'] = user['role_title'] or 'Job Seeker'
    session['user_plan'] = user['plan'] or 'free'
    session['is_admin'] = bool(user['is_admin'])

    logger.info(f"User logged in: {email}")
    return jsonify({'message': 'Login successful', 'user': {
        'id': user['id'], 'name': user['name'], 'email': user['email'], 'is_admin': bool(user['is_admin'])
    }})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': 'Logged out'})

@app.route('/api/auth/me')
def api_me():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    plan_key = session.get('user_plan', 'free')
    plan = PLANS.get(plan_key, PLANS['free'])
    uid = current_user_id()
    app_count = db_fetchone("SELECT COUNT(*) as cnt FROM applications WHERE user_id=%s", (uid,))
    return jsonify({
        'id': session['user_id'],
        'name': session.get('user_name', ''),
        'email': session.get('user_email', ''),
        'role_title': session.get('user_role', 'Job Seeker'),
        'plan': plan_key,
        'plan_name': plan['name'],
        'plan_limits': plan,
        'app_count': app_count['cnt'],
        'is_admin': session.get('is_admin', False),
        'impersonating': session.get('impersonating', False),
    })

# ── Password Reset API ───────────────────────────────────────────────────────
@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    d = request.get_json()
    email = (d.get('email') or '').strip().lower()

    ip = request.remote_addr or 'unknown'
    if rate_limit(f'forgot:{ip}', max_requests=3, window=300):
        return jsonify({'error': 'Too many requests. Please wait 5 minutes.'}), 429

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = db_fetchone("SELECT id, name FROM users WHERE email=%s", (email,))

    # Always return success (don't reveal if email exists)
    if not user:
        logger.info(f"Password reset requested for non-existent email: {email}")
        return jsonify({
            'message': 'If an account with that email exists, a reset link has been generated.',
            'demo_mode': True,
            'reset_link': None,
        })

    # Generate secure token
    token = secrets.token_urlsafe(48)
    if IS_POSTGRES:
        expires = "NOW() + INTERVAL '1 hour'"
        db_execute(f"INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, {expires})",
                   (user['id'], token))
    else:
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        db_execute("INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)",
                   (user['id'], token, expires.isoformat()))
    db_commit()

    # Build reset link
    host = request.host_url.rstrip('/')
    reset_link = f"{host}/reset-password?token={token}"

    logger.info(f"Password reset token generated for user {user['id']}")

    # In production, send email here via SendGrid/SES/etc.
    # For now, return the link directly (demo mode)
    return jsonify({
        'message': 'If an account with that email exists, a reset link has been generated.',
        'demo_mode': True,
        'reset_link': reset_link,
        'note': 'In production, this link would be sent via email. Copy this link to reset your password.',
    })

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    d = request.get_json()
    token = (d.get('token') or '').strip()
    password = d.get('password') or ''

    if not token or not password:
        return jsonify({'error': 'Token and password are required'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if IS_POSTGRES:
        reset = db_fetchone(
            "SELECT * FROM password_resets WHERE token=%s AND used=FALSE AND expires_at > NOW()",
            (token,))
    else:
        reset = db_fetchone(
            "SELECT * FROM password_resets WHERE token=%s AND used=0 AND expires_at > datetime('now')",
            (token,))

    if not reset:
        return jsonify({'error': 'Invalid or expired reset link. Please request a new one.'}), 400

    # Update password
    hashed = hash_password(password)
    db_execute("UPDATE users SET password=%s WHERE id=%s", (hashed, reset['user_id']))
    # Mark token as used
    if IS_POSTGRES:
        db_execute("UPDATE password_resets SET used=TRUE WHERE id=%s", (reset['id'],))
    else:
        db_execute("UPDATE password_resets SET used=1 WHERE id=%s", (reset['id'],))
    db_commit()

    logger.info(f"Password reset completed for user {reset['user_id']}")
    return jsonify({'message': 'Password has been reset successfully. You can now log in.'})

# ── Change Password (logged-in users) ────────────────────────────────────────
@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    d = request.get_json()
    current = d.get('current_password') or ''
    new_pass = d.get('new_password') or ''

    if not current or not new_pass:
        return jsonify({'error': 'Current and new password are required'}), 400
    if len(new_pass) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    uid = current_user_id()
    user = db_fetchone("SELECT password FROM users WHERE id=%s", (uid,))
    if not user or not verify_password(user['password'], current):
        return jsonify({'error': 'Current password is incorrect'}), 401

    hashed = hash_password(new_pass)
    db_execute("UPDATE users SET password=%s WHERE id=%s", (hashed, uid))
    db_commit()

    return jsonify({'message': 'Password changed successfully'})

# ── Plan / Billing API ────────────────────────────────────────────────────────
@app.route('/api/plans')
def get_plans():
    return jsonify(PLANS)

@app.route('/api/billing/checkout', methods=['POST'])
@login_required
def create_checkout():
    d = request.get_json()
    plan = d.get('plan', 'pro')
    if plan not in ('pro', 'premium'):
        return jsonify({'error': 'Invalid plan'}), 400

    uid = current_user_id()
    if IS_POSTGRES:
        db_execute("UPDATE users SET plan=%s, plan_started=NOW() WHERE id=%s", (plan, uid))
    else:
        db_execute("UPDATE users SET plan=%s, plan_started=datetime('now') WHERE id=%s", (plan, uid))
    db_execute("INSERT INTO payments (user_id, plan, amount, status) VALUES (%s,%s,%s,%s)",
               (uid, plan, PLANS[plan]['price'], 'completed'))
    db_commit()
    session['user_plan'] = plan

    return jsonify({
        'message': f'Upgraded to {PLANS[plan]["name"]} plan!',
        'plan': plan, 'demo': True,
        'note': 'In production, this would redirect to Stripe Checkout.',
    })

@app.route('/api/billing/downgrade', methods=['POST'])
@login_required
def downgrade():
    uid = current_user_id()
    db_execute("UPDATE users SET plan='free' WHERE id=%s", (uid,))
    db_commit()
    session['user_plan'] = 'free'
    return jsonify({'message': 'Downgraded to Free plan', 'plan': 'free'})

@app.route('/api/billing/history')
@login_required
def billing_history():
    uid = current_user_id()
    rows = db_fetchall("SELECT * FROM payments WHERE user_id=%s ORDER BY created_at DESC", (uid,))
    return jsonify(rows)

@app.route('/api/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    return jsonify({'received': True})

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/pipeline')
@login_required
def pipeline():
    return render_template('pipeline.html')

@app.route('/applications')
@login_required
def applications():
    return render_template('applications.html')

@app.route('/ai-assistant')
@login_required
def ai_assistant():
    return render_template('ai.html')

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')

@app.route('/pricing')
@login_required
def pricing():
    return render_template('pricing.html')

@app.route('/billing')
@login_required
def billing():
    return render_template('billing.html')

# ── API: Applications ─────────────────────────────────────────────────────────
@app.route('/api/applications', methods=['GET'])
@login_required
def get_applications():
    uid = current_user_id()
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'date_desc')

    sql = "SELECT * FROM applications WHERE user_id=%s"
    params = [uid]
    if status:
        sql += " AND status = %s"
        params.append(status)
    if search:
        sql += " AND (company LIKE %s OR role LIKE %s OR notes LIKE %s)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    order = {'date_desc': 'created_at DESC', 'date_asc': 'created_at ASC',
             'company': 'company ASC', 'salary': 'salary DESC'}.get(sort, 'created_at DESC')
    sql += f" ORDER BY {order}"
    rows = db_fetchall(sql, params)
    return jsonify(rows)

@app.route('/api/applications/<int:app_id>', methods=['GET'])
@login_required
def get_application(app_id):
    uid = current_user_id()
    app_row = db_fetchone("SELECT * FROM applications WHERE id=%s AND user_id=%s", (app_id, uid))
    if not app_row:
        return jsonify({'error': 'Not found'}), 404
    result = dict(app_row)
    result['timeline'] = db_fetchall(
        "SELECT * FROM timeline WHERE app_id=%s ORDER BY created_at DESC", (app_id,))
    result['contacts'] = db_fetchall("SELECT * FROM contacts WHERE app_id=%s", (app_id,))
    return jsonify(result)

@app.route('/api/applications', methods=['POST'])
@login_required
def create_application():
    uid = current_user_id()
    plan = get_user_plan()
    count = db_fetchone("SELECT COUNT(*) as cnt FROM applications WHERE user_id=%s", (uid,))
    if not session.get('is_admin') and count['cnt'] >= plan['app_limit']:
        return jsonify({
            'error': 'upgrade_required',
            'message': f'You have reached the {plan["app_limit"]} application limit on the Free plan. Upgrade to Pro for unlimited tracking!',
            'feature': 'app_limit',
            'current_plan': session.get('user_plan', 'free'),
            'current_count': count['cnt'],
            'limit': plan['app_limit'],
        }), 403

    d = request.get_json()
    company = (d.get('company') or '').strip()
    if not company:
        return jsonify({'error': 'Company required'}), 400
    if len(company) > 200:
        return jsonify({'error': 'Company name is too long'}), 400

    if IS_POSTGRES:
        cur = db_execute(
            """INSERT INTO applications (user_id,company,role,status,date_applied,salary,source,location,followup,priority,job_url,notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (uid, company, d.get('role', ''), d.get('status', 'Applied'),
             d.get('date_applied', date.today().isoformat()),
             d.get('salary', ''), d.get('source', 'LinkedIn'),
             d.get('location', ''), d.get('followup'),
             d.get('priority', 'medium'), d.get('job_url', ''), d.get('notes', '')))
        app_id = cur.fetchone()['id']
    else:
        cur = db_execute(
            """INSERT INTO applications (user_id,company,role,status,date_applied,salary,source,location,followup,priority,job_url,notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (uid, company, d.get('role', ''), d.get('status', 'Applied'),
             d.get('date_applied', date.today().isoformat()),
             d.get('salary', ''), d.get('source', 'LinkedIn'),
             d.get('location', ''), d.get('followup'),
             d.get('priority', 'medium'), d.get('job_url', ''), d.get('notes', '')))
        app_id = db_lastrowid(cur)

    db_execute("INSERT INTO timeline (app_id, action) VALUES (%s,%s)", (app_id, 'Application tracked'))
    db_commit()
    return jsonify({'id': app_id, 'message': 'Created'}), 201

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
@login_required
def update_application(app_id):
    uid = current_user_id()
    d = request.get_json()
    existing = db_fetchone("SELECT * FROM applications WHERE id=%s AND user_id=%s", (app_id, uid))
    if not existing:
        return jsonify({'error': 'Not found'}), 404

    old_status = existing['status']
    if IS_POSTGRES:
        db_execute(
            """UPDATE applications SET company=%s,role=%s,status=%s,date_applied=%s,salary=%s,source=%s,
               location=%s,followup=%s,priority=%s,job_url=%s,notes=%s,updated_at=NOW() WHERE id=%s AND user_id=%s""",
            (d.get('company', existing['company']), d.get('role', existing['role']),
             d.get('status', existing['status']), d.get('date_applied', existing['date_applied']),
             d.get('salary', existing['salary']), d.get('source', existing['source']),
             d.get('location', existing['location']), d.get('followup', existing['followup']),
             d.get('priority', existing['priority']), d.get('job_url', existing['job_url']),
             d.get('notes', existing['notes']), app_id, uid))
    else:
        db_execute(
            """UPDATE applications SET company=%s,role=%s,status=%s,date_applied=%s,salary=%s,source=%s,
               location=%s,followup=%s,priority=%s,job_url=%s,notes=%s,updated_at=datetime('now') WHERE id=%s AND user_id=%s""",
            (d.get('company', existing['company']), d.get('role', existing['role']),
             d.get('status', existing['status']), d.get('date_applied', existing['date_applied']),
             d.get('salary', existing['salary']), d.get('source', existing['source']),
             d.get('location', existing['location']), d.get('followup', existing['followup']),
             d.get('priority', existing['priority']), d.get('job_url', existing['job_url']),
             d.get('notes', existing['notes']), app_id, uid))

    if d.get('status') and d['status'] != old_status:
        db_execute("INSERT INTO timeline (app_id, action) VALUES (%s,%s)", (app_id, f"Status -> {d['status']}"))
    db_commit()
    return jsonify({'message': 'Updated'})

@app.route('/api/applications/<int:app_id>/status', methods=['PATCH'])
@login_required
def update_status(app_id):
    uid = current_user_id()
    d = request.get_json()
    existing = db_fetchone("SELECT status FROM applications WHERE id=%s AND user_id=%s", (app_id, uid))
    if not existing:
        return jsonify({'error': 'Not found'}), 404
    old_status = existing['status']
    new_status = d.get('status')
    if IS_POSTGRES:
        db_execute("UPDATE applications SET status=%s, updated_at=NOW() WHERE id=%s AND user_id=%s", (new_status, app_id, uid))
    else:
        db_execute("UPDATE applications SET status=%s, updated_at=datetime('now') WHERE id=%s AND user_id=%s", (new_status, app_id, uid))
    if new_status != old_status:
        db_execute("INSERT INTO timeline (app_id, action) VALUES (%s,%s)", (app_id, f"Status -> {new_status}"))
    db_commit()
    return jsonify({'message': 'Updated', 'status': new_status})

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
@login_required
def delete_application(app_id):
    uid = current_user_id()
    if not db_fetchone("SELECT id FROM applications WHERE id=%s AND user_id=%s", (app_id, uid)):
        return jsonify({'error': 'Not found'}), 404
    db_execute("DELETE FROM applications WHERE id=%s AND user_id=%s", (app_id, uid))
    db_commit()
    return jsonify({'message': 'Deleted'})

@app.route('/api/applications/<int:app_id>/timeline', methods=['POST'])
@login_required
def add_timeline(app_id):
    uid = current_user_id()
    if not db_fetchone("SELECT id FROM applications WHERE id=%s AND user_id=%s", (app_id, uid)):
        return jsonify({'error': 'Not found'}), 404
    d = request.get_json()
    db_execute("INSERT INTO timeline (app_id, action, note) VALUES (%s,%s,%s)",
               (app_id, d.get('action', 'Note'), d.get('note', '')))
    db_commit()
    return jsonify({'message': 'Added'})

# ── API: Stats ────────────────────────────────────────────────────────────────
@app.route('/api/stats')
@login_required
def get_stats():
    uid = current_user_id()
    plan = get_user_plan()

    rows = db_fetchall("SELECT status, COUNT(*) as cnt FROM applications WHERE user_id=%s GROUP BY status", (uid,))
    stats = {r['status']: r['cnt'] for r in rows}
    total = sum(stats.values())
    interviews = stats.get('Interview', 0)
    offers = stats.get('Offer', 0)
    response_rate = round((interviews + offers) / total * 100) if total else 0

    result = {
        'total': total, 'by_status': stats, 'response_rate': response_rate,
        'applied': stats.get('Applied', 0), 'interview': stats.get('Interview', 0),
        'offer': stats.get('Offer', 0), 'rejected': stats.get('Rejected', 0),
        'ghosted': stats.get('Ghosted', 0), 'saved': stats.get('Saved', 0),
        'plan': session.get('user_plan', 'free'), 'plan_limits': plan,
    }

    if plan.get('advanced_analytics'):
        result['sources'] = db_fetchall(
            "SELECT source, COUNT(*) as cnt FROM applications WHERE user_id=%s GROUP BY source ORDER BY cnt DESC", (uid,))
        month_expr = month_sql('date_applied')
        result['trend'] = db_fetchall(f"""
            SELECT {month_expr} as month, COUNT(*) as cnt
            FROM applications WHERE user_id=%s AND date_applied IS NOT NULL
            GROUP BY month ORDER BY month DESC LIMIT 6""", (uid,))
    else:
        result['sources'] = []
        result['trend'] = []

    today = date.today().isoformat()
    result['followups'] = db_fetchall("""
        SELECT id, company, role, followup FROM applications
        WHERE user_id=%s AND followup IS NOT NULL AND followup <= %s AND status NOT IN ('Rejected','Ghosted','Offer')
        ORDER BY followup ASC LIMIT 5""", (uid, today))

    return jsonify(result)

# ── API: Contacts (gated) ─────────────────────────────────────────────────────
@app.route('/api/applications/<int:app_id>/contacts', methods=['POST'])
@login_required
@require_feature('contacts')
def add_contact(app_id):
    uid = current_user_id()
    if not db_fetchone("SELECT id FROM applications WHERE id=%s AND user_id=%s", (app_id, uid)):
        return jsonify({'error': 'Not found'}), 404
    d = request.get_json()
    db_execute("INSERT INTO contacts (app_id, name, role, email, linkedin, notes) VALUES (%s,%s,%s,%s,%s,%s)",
               (app_id, d.get('name'), d.get('role'), d.get('email'), d.get('linkedin'), d.get('notes')))
    db_commit()
    return jsonify({'message': 'Added'})

# ── API: Export (gated) ───────────────────────────────────────────────────────
@app.route('/api/export/csv')
@login_required
@require_feature('csv_export')
def export_csv():
    uid = current_user_id()
    rows = db_fetchall("SELECT * FROM applications WHERE user_id=%s ORDER BY created_at DESC", (uid,))
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Company', 'Role', 'Status', 'Date Applied', 'Salary', 'Source', 'Location', 'Follow-up', 'Priority', 'Notes', 'Created'])
    for r in rows:
        writer.writerow([r['id'], r['company'], r['role'], r['status'], r.get('date_applied', ''),
                         r.get('salary', ''), r.get('source', ''), r.get('location', ''),
                         r.get('followup', ''), r.get('priority', ''), r.get('notes', ''), r['created_at']])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=hireflow-export.csv'})

# ── Admin Pages ───────────────────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html')

@app.route('/admin/users')
@admin_required
def admin_users():
    return render_template('admin_users.html')

# ── Admin API ─────────────────────────────────────────────────────────────────
@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    total_users = db_fetchone("SELECT COUNT(*) as cnt FROM users")['cnt']
    total_apps = db_fetchone("SELECT COUNT(*) as cnt FROM applications")['cnt']
    total_payments = db_fetchone("SELECT COUNT(*) as cnt FROM payments")['cnt']
    total_revenue = db_fetchone("SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE status='completed'")['total']

    by_plan = db_fetchall("SELECT plan, COUNT(*) as cnt FROM users GROUP BY plan ORDER BY cnt DESC")
    by_status = db_fetchall("SELECT status, COUNT(*) as cnt FROM applications GROUP BY status ORDER BY cnt DESC")

    date_expr = date_only_sql('created_at')
    signups_trend = db_fetchall(f"""
        SELECT {date_expr} as day, COUNT(*) as cnt FROM users
        WHERE {date_sql('created_at', 14)}
        GROUP BY day ORDER BY day ASC""")

    month_expr = month_sql('created_at')
    revenue_trend = db_fetchall(f"""
        SELECT {month_expr} as month, SUM(amount) as total, COUNT(*) as cnt
        FROM payments WHERE status='completed'
        GROUP BY month ORDER BY month DESC LIMIT 6""")

    top_users = db_fetchall("""
        SELECT u.id, u.name, u.email, u.plan, u.is_admin, u.is_blocked, u.created_at,
               COUNT(a.id) as app_count
        FROM users u LEFT JOIN applications a ON a.user_id = u.id
        GROUP BY u.id, u.name, u.email, u.plan, u.is_admin, u.is_blocked, u.created_at
        ORDER BY app_count DESC LIMIT 10""")

    recent_users = db_fetchall(
        "SELECT id, name, email, plan, is_admin, is_blocked, created_at FROM users ORDER BY created_at DESC LIMIT 10")

    return jsonify({
        'total_users': total_users, 'total_apps': total_apps,
        'total_payments': total_payments, 'total_revenue': total_revenue,
        'by_plan': by_plan, 'by_status': by_status,
        'signups_trend': signups_trend, 'revenue_trend': revenue_trend,
        'top_users': top_users, 'recent_users': recent_users,
    })

@app.route('/api/admin/users')
@admin_required
def admin_list_users():
    search = request.args.get('search', '')
    plan_filter = request.args.get('plan', '')
    sql = """SELECT u.id, u.name, u.email, u.role_title, u.plan, u.is_admin, u.is_blocked, u.created_at,
             COUNT(a.id) as app_count
             FROM users u LEFT JOIN applications a ON a.user_id = u.id WHERE 1=1"""
    params = []
    if search:
        sql += " AND (u.name LIKE %s OR u.email LIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    if plan_filter:
        sql += " AND u.plan = %s"
        params.append(plan_filter)
    sql += " GROUP BY u.id, u.name, u.email, u.role_title, u.plan, u.is_admin, u.is_blocked, u.created_at ORDER BY u.created_at DESC"
    rows = db_fetchall(sql, params)
    return jsonify(rows)

@app.route('/api/admin/users/<int:uid>', methods=['GET'])
@admin_required
def admin_get_user(uid):
    user = db_fetchone("""SELECT u.id, u.name, u.email, u.role_title, u.plan, u.is_admin, u.is_blocked,
                         u.stripe_customer_id, u.plan_started, u.created_at,
                         COUNT(a.id) as app_count
                         FROM users u LEFT JOIN applications a ON a.user_id = u.id
                         WHERE u.id=%s
                         GROUP BY u.id, u.name, u.email, u.role_title, u.plan, u.is_admin, u.is_blocked, u.stripe_customer_id, u.plan_started, u.created_at""", (uid,))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    result = dict(user)
    result['payments'] = db_fetchall("SELECT * FROM payments WHERE user_id=%s ORDER BY created_at DESC", (uid,))
    result['recent_apps'] = db_fetchall(
        "SELECT id, company, role, status, created_at FROM applications WHERE user_id=%s ORDER BY created_at DESC LIMIT 10", (uid,))
    return jsonify(result)

@app.route('/api/admin/users/<int:uid>', methods=['PUT'])
@admin_required
def admin_update_user(uid):
    d = request.get_json()
    user = db_fetchone("SELECT * FROM users WHERE id=%s", (uid,))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if uid == current_user_id() and 'is_admin' in d and not d['is_admin']:
        return jsonify({'error': 'Cannot remove your own admin access'}), 400

    is_admin_val = True if d.get('is_admin', user['is_admin']) else False
    is_blocked_val = True if d.get('is_blocked', user['is_blocked']) else False
    if not IS_POSTGRES:
        is_admin_val = 1 if is_admin_val else 0
        is_blocked_val = 1 if is_blocked_val else 0

    db_execute("""UPDATE users SET name=%s, email=%s, role_title=%s, plan=%s, is_admin=%s, is_blocked=%s WHERE id=%s""",
        (d.get('name', user['name']), d.get('email', user['email']),
         d.get('role_title', user['role_title']), d.get('plan', user['plan']),
         is_admin_val, is_blocked_val, uid))
    db_commit()
    return jsonify({'message': 'User updated'})

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@admin_required
def admin_delete_user(uid):
    if uid == current_user_id():
        return jsonify({'error': 'Cannot delete your own account'}), 400
    if not db_fetchone("SELECT id FROM users WHERE id=%s", (uid,)):
        return jsonify({'error': 'User not found'}), 404
    db_execute("DELETE FROM applications WHERE user_id=%s", (uid,))
    db_execute("DELETE FROM payments WHERE user_id=%s", (uid,))
    db_execute("DELETE FROM users WHERE id=%s", (uid,))
    db_commit()
    return jsonify({'message': 'User and all their data deleted'})

@app.route('/api/admin/users/<int:uid>/impersonate', methods=['POST'])
@admin_required
def admin_impersonate(uid):
    user = db_fetchone("SELECT * FROM users WHERE id=%s", (uid,))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    real_admin_id = current_user_id()
    session['real_admin_id'] = real_admin_id
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']
    session['user_role'] = user['role_title'] or 'Job Seeker'
    session['user_plan'] = user['plan'] or 'free'
    session['is_admin'] = bool(user['is_admin'])
    session['impersonating'] = True
    return jsonify({'message': f'Now impersonating {user["name"]}', 'user_id': user['id']})

@app.route('/api/admin/stop-impersonating', methods=['POST'])
@login_required
def stop_impersonating():
    real_id = session.get('real_admin_id')
    if not real_id:
        return jsonify({'error': 'Not impersonating anyone'}), 400
    admin = db_fetchone("SELECT * FROM users WHERE id=%s", (real_id,))
    if not admin:
        return jsonify({'error': 'Admin account not found'}), 404
    session.pop('real_admin_id', None)
    session.pop('impersonating', None)
    session['user_id'] = admin['id']
    session['user_name'] = admin['name']
    session['user_email'] = admin['email']
    session['user_role'] = admin['role_title'] or 'Job Seeker'
    session['user_plan'] = admin['plan'] or 'free'
    session['is_admin'] = bool(admin['is_admin'])
    return jsonify({'message': 'Switched back to admin account'})

@app.route('/api/admin/users/<int:uid>/set-plan', methods=['POST'])
@admin_required
def admin_set_plan(uid):
    d = request.get_json()
    plan = d.get('plan', 'free')
    if plan not in PLANS:
        return jsonify({'error': 'Invalid plan'}), 400
    if IS_POSTGRES:
        db_execute("UPDATE users SET plan=%s, plan_started=NOW() WHERE id=%s", (plan, uid))
    else:
        db_execute("UPDATE users SET plan=%s, plan_started=datetime('now') WHERE id=%s", (plan, uid))
    db_commit()
    return jsonify({'message': f'Plan set to {PLANS[plan]["name"]}'})

@app.route('/api/admin/users/<int:uid>/toggle-block', methods=['POST'])
@admin_required
def admin_toggle_block(uid):
    if uid == current_user_id():
        return jsonify({'error': 'Cannot block yourself'}), 400
    user = db_fetchone("SELECT is_blocked FROM users WHERE id=%s", (uid,))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    new_val = not bool(user['is_blocked'])
    if IS_POSTGRES:
        db_execute("UPDATE users SET is_blocked=%s WHERE id=%s", (new_val, uid))
    else:
        db_execute("UPDATE users SET is_blocked=%s WHERE id=%s", (1 if new_val else 0, uid))
    db_commit()
    return jsonify({'message': 'User blocked' if new_val else 'User unblocked', 'is_blocked': new_val})

@app.route('/api/admin/users/<int:uid>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_admin(uid):
    if uid == current_user_id():
        return jsonify({'error': 'Cannot modify your own admin status'}), 400
    user = db_fetchone("SELECT is_admin FROM users WHERE id=%s", (uid,))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    new_val = not bool(user['is_admin'])
    if IS_POSTGRES:
        db_execute("UPDATE users SET is_admin=%s WHERE id=%s", (new_val, uid))
    else:
        db_execute("UPDATE users SET is_admin=%s WHERE id=%s", (1 if new_val else 0, uid))
    db_commit()
    return jsonify({'message': 'Admin granted' if new_val else 'Admin revoked', 'is_admin': new_val})

@app.route('/api/admin/all-applications')
@admin_required
def admin_all_applications():
    rows = db_fetchall("""SELECT a.*, u.name as user_name, u.email as user_email
                         FROM applications a JOIN users u ON a.user_id = u.id
                         ORDER BY a.created_at DESC LIMIT 100""")
    return jsonify(rows)

# ── Admin: Reset user password ────────────────────────────────────────────────
@app.route('/api/admin/users/<int:uid>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(uid):
    d = request.get_json()
    new_pass = d.get('password', '')
    if len(new_pass) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    user = db_fetchone("SELECT id FROM users WHERE id=%s", (uid,))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    hashed = hash_password(new_pass)
    db_execute("UPDATE users SET password=%s WHERE id=%s", (hashed, uid))
    db_commit()
    return jsonify({'message': 'Password has been reset'})

# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV') != 'production'
    logger.info(f"HireFlow Pro starting on port {port} (debug={debug})")
    print(f"\n  HireFlow Pro running!")
    print(f"  Open: http://127.0.0.1:{port}\n")
    app.run(debug=debug, port=port, host='0.0.0.0')
