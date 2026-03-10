from flask import Flask, jsonify, request, render_template, g
import sqlite3, json, os, re
from datetime import datetime, date, timedelta

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'hireflow.db')

# ── Database ─────────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS applications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company     TEXT NOT NULL,
            role        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'Applied',
            date_applied TEXT,
            salary      TEXT,
            source      TEXT DEFAULT 'LinkedIn',
            location    TEXT,
            followup    TEXT,
            priority    TEXT DEFAULT 'medium',
            job_url     TEXT,
            notes       TEXT,
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
    """)
    # Seed demo data if empty
    count = db.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    if count == 0:
        demo = [
            ('Salesforce', 'Platform Developer', 'Applied', '2026-03-08', 'AED 20k/mo', 'LinkedIn', 'Dubai, UAE', '2026-03-15', 'high', 'https://salesforce.com/careers', 'JD matches perfectly. Salesforce PD1 requirement — studying via Trailhead.'),
            ('Microsoft', 'Senior .NET Backend Engineer', 'Interview', '2026-03-01', 'AED 22k/mo', 'Company Website', 'Abu Dhabi, UAE', '2026-03-12', 'high', 'https://careers.microsoft.com', 'Round 1 cleared. Technical design round scheduled. Prep system design.'),
            ('Thoughtworks', 'Senior Backend Developer', 'Applied', '2026-03-05', '₹28 LPA', 'Naukri', 'Bangalore, India', '2026-03-14', 'high', '', 'Strong .NET focus. Remote option possible after 6 months.'),
            ('Oracle', 'Cloud Backend Developer', 'Rejected', '2026-02-15', 'AED 16k/mo', 'Indeed', 'Dubai, UAE', None, 'medium', '', 'Wanted Java primarily. Feedback: strong profile but wrong stack.'),
            ('Wipro', 'Senior .NET Developer', 'Ghosted', '2026-02-01', '₹22 LPA', 'LinkedIn', 'Hyderabad, India', None, 'low', '', 'No response in 5 weeks.'),
            ('Mulesoft (Salesforce)', 'Integration Developer', 'Saved', '2026-03-10', '₹30 LPA', 'LinkedIn', 'Bangalore, India', '2026-03-18', 'high', '', 'Perfect for RabbitMQ + event-driven background. Apply this week!'),
            ('HCL Tech', '.NET Architect', 'Applied', '2026-03-07', '₹32 LPA', 'Naukri', 'Chennai, India', '2026-03-17', 'medium', '', 'Good package, hybrid work policy.'),
        ]
        for row in demo:
            db.execute("""INSERT INTO applications (company,role,status,date_applied,salary,source,location,followup,priority,job_url,notes)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?)""", row)
        db.commit()
        # Add timeline entries for demo apps
        apps = db.execute("SELECT id, status, created_at FROM applications").fetchall()
        for a in apps:
            db.execute("INSERT INTO timeline (app_id, action) VALUES (?,?)", (a['id'], 'Application tracked'))
            if a['status'] == 'Interview':
                db.execute("INSERT INTO timeline (app_id, action) VALUES (?,?)", (a['id'], 'Status → Interview'))
            elif a['status'] == 'Rejected':
                db.execute("INSERT INTO timeline (app_id, action) VALUES (?,?)", (a['id'], 'Status → Rejected'))
        db.commit()
    db.close()

# ── Helpers ──────────────────────────────────────────────────────────────────
def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

# ── Pages ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard(): return render_template('dashboard.html')

@app.route('/pipeline')
def pipeline(): return render_template('pipeline.html')

@app.route('/applications')
def applications(): return render_template('applications.html')

@app.route('/ai-assistant')
def ai_assistant(): return render_template('ai.html')

@app.route('/analytics')
def analytics(): return render_template('analytics.html')

# ── API: Applications ────────────────────────────────────────────────────────
@app.route('/api/applications', methods=['GET'])
def get_applications():
    db = get_db()
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    sort   = request.args.get('sort', 'date_desc')

    sql = "SELECT * FROM applications WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"; params.append(status)
    if search:
        sql += " AND (company LIKE ? OR role LIKE ? OR notes LIKE ?)";
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    order = {'date_desc':'created_at DESC','date_asc':'created_at ASC',
             'company':'company ASC','salary':'salary DESC'}.get(sort,'created_at DESC')
    sql += f" ORDER BY {order}"
    rows = db.execute(sql, params).fetchall()
    return jsonify(rows_to_list(rows))

@app.route('/api/applications/<int:app_id>', methods=['GET'])
def get_application(app_id):
    db = get_db()
    app_row = db.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not app_row: return jsonify({'error':'Not found'}), 404
    result = row_to_dict(app_row)
    result['timeline'] = rows_to_list(db.execute(
        "SELECT * FROM timeline WHERE app_id=? ORDER BY created_at DESC", (app_id,)).fetchall())
    result['contacts'] = rows_to_list(db.execute(
        "SELECT * FROM contacts WHERE app_id=?", (app_id,)).fetchall())
    return jsonify(result)

@app.route('/api/applications', methods=['POST'])
def create_application():
    db = get_db()
    d = request.get_json()
    if not d.get('company'): return jsonify({'error':'Company required'}), 400
    cur = db.execute("""INSERT INTO applications (company,role,status,date_applied,salary,source,location,followup,priority,job_url,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (d.get('company'), d.get('role',''), d.get('status','Applied'),
         d.get('date_applied', date.today().isoformat()),
         d.get('salary',''), d.get('source','LinkedIn'),
         d.get('location',''), d.get('followup'),
         d.get('priority','medium'), d.get('job_url',''), d.get('notes','')))
    app_id = cur.lastrowid
    db.execute("INSERT INTO timeline (app_id, action) VALUES (?,?)", (app_id, 'Application tracked'))
    db.commit()
    return jsonify({'id': app_id, 'message': 'Created'}), 201

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    db = get_db()
    d = request.get_json()
    existing = db.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not existing: return jsonify({'error':'Not found'}), 404

    old_status = existing['status']
    db.execute("""UPDATE applications SET company=?,role=?,status=?,date_applied=?,salary=?,source=?,
                  location=?,followup=?,priority=?,job_url=?,notes=?,updated_at=datetime('now') WHERE id=?""",
        (d.get('company', existing['company']), d.get('role', existing['role']),
         d.get('status', existing['status']), d.get('date_applied', existing['date_applied']),
         d.get('salary', existing['salary']), d.get('source', existing['source']),
         d.get('location', existing['location']), d.get('followup', existing['followup']),
         d.get('priority', existing['priority']), d.get('job_url', existing['job_url']),
         d.get('notes', existing['notes']), app_id))
    if d.get('status') and d['status'] != old_status:
        db.execute("INSERT INTO timeline (app_id, action) VALUES (?,?)",
                   (app_id, f"Status → {d['status']}"))
    db.commit()
    return jsonify({'message': 'Updated'})

@app.route('/api/applications/<int:app_id>/status', methods=['PATCH'])
def update_status(app_id):
    db = get_db()
    d = request.get_json()
    existing = db.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()
    if not existing: return jsonify({'error':'Not found'}), 404
    old_status = existing['status']
    new_status = d.get('status')
    db.execute("UPDATE applications SET status=?, updated_at=datetime('now') WHERE id=?", (new_status, app_id))
    if new_status != old_status:
        db.execute("INSERT INTO timeline (app_id, action) VALUES (?,?)", (app_id, f"Status → {new_status}"))
    db.commit()
    return jsonify({'message': 'Updated', 'status': new_status})

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    db = get_db()
    if not db.execute("SELECT id FROM applications WHERE id=?", (app_id,)).fetchone():
        return jsonify({'error':'Not found'}), 404
    db.execute("DELETE FROM applications WHERE id=?", (app_id,))
    db.commit()
    return jsonify({'message': 'Deleted'})

@app.route('/api/applications/<int:app_id>/timeline', methods=['POST'])
def add_timeline(app_id):
    db = get_db()
    d = request.get_json()
    db.execute("INSERT INTO timeline (app_id, action, note) VALUES (?,?,?)",
               (app_id, d.get('action','Note'), d.get('note','')))
    db.commit()
    return jsonify({'message': 'Added'})

# ── API: Stats ────────────────────────────────────────────────────────────────
@app.route('/api/stats')
def get_stats():
    db = get_db()
    rows = db.execute("SELECT status, COUNT(*) as cnt FROM applications GROUP BY status").fetchall()
    stats = {r['status']: r['cnt'] for r in rows}
    total = sum(stats.values())
    interviews = stats.get('Interview', 0)
    offers = stats.get('Offer', 0)
    response_rate = round((interviews + offers) / total * 100) if total else 0

    # Source breakdown
    sources = rows_to_list(db.execute(
        "SELECT source, COUNT(*) as cnt FROM applications GROUP BY source ORDER BY cnt DESC").fetchall())

    # Monthly trend (last 6 months)
    trend = rows_to_list(db.execute("""
        SELECT strftime('%Y-%m', date_applied) as month, COUNT(*) as cnt
        FROM applications WHERE date_applied IS NOT NULL
        GROUP BY month ORDER BY month DESC LIMIT 6""").fetchall())

    # Upcoming follow-ups
    today = date.today().isoformat()
    followups = rows_to_list(db.execute("""
        SELECT id, company, role, followup FROM applications
        WHERE followup IS NOT NULL AND followup <= ? AND status NOT IN ('Rejected','Ghosted','Offer')
        ORDER BY followup ASC LIMIT 5""", (today,)).fetchall())

    return jsonify({
        'total': total, 'by_status': stats,
        'response_rate': response_rate,
        'sources': sources, 'trend': trend,
        'followups': followups,
        'applied': stats.get('Applied',0), 'interview': stats.get('Interview',0),
        'offer': stats.get('Offer',0), 'rejected': stats.get('Rejected',0),
        'ghosted': stats.get('Ghosted',0), 'saved': stats.get('Saved',0),
    })

# ── API: Contacts ─────────────────────────────────────────────────────────────
@app.route('/api/applications/<int:app_id>/contacts', methods=['POST'])
def add_contact(app_id):
    db = get_db()
    d = request.get_json()
    db.execute("INSERT INTO contacts (app_id, name, role, email, linkedin, notes) VALUES (?,?,?,?,?,?)",
               (app_id, d.get('name'), d.get('role'), d.get('email'), d.get('linkedin'), d.get('notes')))
    db.commit()
    return jsonify({'message': 'Added'})

# ── API: Export ───────────────────────────────────────────────────────────────
@app.route('/api/export/csv')
def export_csv():
    db = get_db()
    rows = db.execute("SELECT * FROM applications ORDER BY created_at DESC").fetchall()
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Company','Role','Status','Date Applied','Salary','Source','Location','Follow-up','Priority','Notes','Created'])
    for r in rows:
        writer.writerow([r['id'],r['company'],r['role'],r['status'],r['date_applied'] or '',
                         r['salary'] or '',r['source'] or '',r['location'] or '',
                         r['followup'] or '',r['priority'] or '',r['notes'] or '',r['created_at']])
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=hireflow-export.csv'})

if __name__ == '__main__':
    init_db()
    print("\n✅  HireFlow Pro backend running!")
    print("🌐  Open: http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
