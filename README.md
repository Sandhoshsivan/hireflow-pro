# HireFlow Pro

**Enterprise-Grade Job Application Tracker with Freemium SaaS Model**

A production-ready, full-stack web application built with Flask that helps job seekers track applications, manage their pipeline, and get AI-powered career insights — complete with multi-user authentication, role-based access control, admin dashboard, and Stripe-ready billing.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Features](#features)
- [Database Design](#database-design)
- [Authentication & Security](#authentication--security)
- [Freemium Plan System](#freemium-plan-system)
- [Admin Panel](#admin-panel)
- [API Reference](#api-reference)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [How We Built It](#how-we-built-it)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Client (Browser)                     │
│  Jinja2 Templates + Vanilla JS + Custom CSS Design System│
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────▼──────────────────────────────┐
│                    Flask Application                     │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │   Auth   │ │   CRUD   │ │  Admin   │ │  Billing   │ │
│  │ Module   │ │   APIs   │ │  Panel   │ │  System    │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘ │
│       │             │            │              │        │
│  ┌────▼─────────────▼────────────▼──────────────▼────┐  │
│  │          Database Abstraction Layer                │  │
│  │   PostgreSQL (production) / SQLite (development)  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  Security: Rate Limiting · Secure Headers · PBKDF2      │
│  Session:  HttpOnly · SameSite · Secure Cookies         │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.11 + Flask 3.1 | REST API, server-side routing, template rendering |
| **Database** | PostgreSQL (prod) / SQLite (dev) | Persistent storage with dual-driver support |
| **WSGI Server** | Gunicorn | Production-grade process manager |
| **Frontend** | Jinja2 + Vanilla JS | Server-rendered templates with dynamic client-side updates |
| **CSS** | Custom design system | Hand-crafted tokens, components, and utility classes |
| **Fonts** | Plus Jakarta Sans + Fira Code | UI text + monospaced data display |
| **Hosting** | Render.com | Free-tier web service + managed PostgreSQL |

---

## Project Structure

```
hireflow/
├── app.py                      # Main application (all routes, models, logic)
├── requirements.txt            # Python dependencies
├── Procfile                    # Gunicorn start command for production
├── render.yaml                 # Render.com infrastructure-as-code blueprint
├── runtime.txt                 # Python version pin
├── .gitignore                  # Excludes venv, db, secrets, caches
│
├── static/
│   ├── css/
│   │   ├── main.css            # Full design system (tokens, layout, components)
│   │   └── auth.css            # Auth page styles (login, register, reset)
│   └── js/
│       └── app.js              # API client, toast, modal, drawer, helpers
│
└── templates/
    ├── base.html               # Master layout (sidebar, nav, user card, scripts)
    ├── login.html              # Login page
    ├── register.html           # Registration page
    ├── forgot_password.html    # Forgot password flow
    ├── reset_password.html     # Set new password via token
    ├── dashboard.html          # KPIs, funnel chart, recent apps
    ├── applications.html       # Full app table + detail drawer
    ├── pipeline.html           # Kanban board view
    ├── analytics.html          # Charts and insights
    ├── ai.html                 # AI career assistant chat
    ├── pricing.html            # 3-tier plan comparison
    ├── billing.html            # Current plan, usage, payment history
    ├── admin.html              # Admin dashboard (stats, charts, tables)
    ├── admin_users.html        # User management CRUD
    ├── index.html              # Root redirect
    ├── partials/
    │   └── app_modal.html      # Shared application create/edit modal
    └── errors/
        ├── 404.html            # Not found page
        └── 500.html            # Server error page
```

---

## Features

### Core Application Tracking
- Full CRUD for job applications (company, role, status, salary, source, location, notes)
- 6 status stages: **Saved → Applied → Interview → Offer → Rejected → Ghosted**
- Priority levels: High / Medium / Low
- Follow-up date reminders with sidebar alerts
- Timeline logging — every status change is automatically recorded
- Contact tracking per application (name, role, email, LinkedIn)

### Dashboard & Analytics
- 5 KPI cards: Total, Applied, Interviews, Offers, Response Rate
- Status distribution funnel chart
- Application sources breakdown
- Monthly trend chart
- Priority distribution
- Recent applications feed
- Follow-up alerts with due dates

### Pipeline (Kanban Board)
- Drag-style column view by status
- Card-based UI showing company, role, salary, date
- Quick-access to application details

### AI Career Assistant
- Chat interface powered by Claude API
- Context-aware — knows your job data and profile
- Career advice, interview tips, resume suggestions

### CSV Export
- One-click download of all applications as CSV
- Includes all fields: company, role, status, dates, salary, source, notes

---

## Database Design

### Entity Relationship

```
users (1) ──── (N) applications (1) ──── (N) timeline
  │                    │
  │                    └──── (N) contacts
  │
  └──── (N) payments
  │
  └──── (N) password_resets
```

### Tables

#### `users`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL / INTEGER PK | Auto-incrementing primary key |
| name | TEXT | Full name |
| email | TEXT UNIQUE | Login email (lowercase, unique) |
| password | TEXT | PBKDF2-SHA256 hash (`salt:hash` format) |
| role_title | TEXT | User's job title (default: "Job Seeker") |
| plan | TEXT | Subscription plan: `free`, `pro`, `premium` |
| plan_started | TIMESTAMP | When current plan was activated |
| stripe_customer_id | TEXT | Stripe customer ID (for production billing) |
| is_admin | BOOLEAN | Admin flag (first user auto-promoted) |
| is_blocked | BOOLEAN | Account suspension flag |
| created_at | TIMESTAMP | Registration timestamp |

#### `applications`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL / INTEGER PK | Primary key |
| user_id | INTEGER FK | Owner (references users.id) |
| company | TEXT | Company name |
| role | TEXT | Job title/role |
| status | TEXT | Applied, Interview, Offer, Rejected, Ghosted, Saved |
| date_applied | TEXT | Application date (ISO format) |
| salary | TEXT | Salary/compensation |
| source | TEXT | Where you found the job |
| location | TEXT | Job location |
| followup | TEXT | Follow-up reminder date |
| priority | TEXT | high, medium, low |
| job_url | TEXT | Link to job posting |
| notes | TEXT | Free-form notes |
| created_at | TIMESTAMP | Record creation |
| updated_at | TIMESTAMP | Last modification |

#### `timeline`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL / INTEGER PK | Primary key |
| app_id | INTEGER FK | References applications.id (CASCADE delete) |
| action | TEXT | Event description (e.g., "Status → Interview") |
| note | TEXT | Optional note |
| created_at | TIMESTAMP | Event timestamp |

#### `contacts`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL / INTEGER PK | Primary key |
| app_id | INTEGER FK | References applications.id (CASCADE delete) |
| name | TEXT | Contact name |
| role | TEXT | Contact's role/title |
| email | TEXT | Contact email |
| linkedin | TEXT | LinkedIn profile URL |
| notes | TEXT | Notes about the contact |

#### `payments`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL / INTEGER PK | Primary key |
| user_id | INTEGER FK | References users.id |
| plan | TEXT | Plan purchased |
| amount | REAL | Payment amount |
| currency | TEXT | Default: USD |
| status | TEXT | completed, pending, failed |
| stripe_session_id | TEXT | Stripe checkout session ID |
| created_at | TIMESTAMP | Payment timestamp |

#### `password_resets`
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL / INTEGER PK | Primary key |
| user_id | INTEGER FK | References users.id |
| token | TEXT UNIQUE | Secure URL-safe token (48 bytes) |
| expires_at | TIMESTAMP | Token expiration (1 hour) |
| used | BOOLEAN | Whether token has been consumed |
| created_at | TIMESTAMP | Request timestamp |

---

## Authentication & Security

### Password Hashing
- **Algorithm**: PBKDF2-SHA256 with 260,000 iterations
- **Salt**: 16-byte random hex per password (`secrets.token_hex(16)`)
- **Storage format**: `salt:hash` (e.g., `a1b2c3...:d4e5f6...`)
- **Comparison**: Constant-time via `secrets.compare_digest()` to prevent timing attacks

### Session Management
- Flask signed cookie sessions with `secret_key`
- `SESSION_COOKIE_HTTPONLY=True` — prevents JavaScript access
- `SESSION_COOKIE_SAMESITE='Lax'` — CSRF protection
- `SESSION_COOKIE_SECURE=True` in production — HTTPS only
- `PERMANENT_SESSION_LIFETIME=7 days` — automatic expiry

### Rate Limiting
- In-memory rate limiter on sensitive endpoints:
  - **Login**: 10 attempts per 5 minutes per IP
  - **Register**: 5 attempts per 5 minutes per IP
  - **Forgot Password**: 3 attempts per 5 minutes per IP

### Security Headers (applied to all responses)
| Header | Value | Purpose |
|--------|-------|---------|
| X-Content-Type-Options | nosniff | Prevents MIME sniffing |
| X-Frame-Options | DENY | Prevents clickjacking |
| X-XSS-Protection | 1; mode=block | XSS filter |
| Referrer-Policy | strict-origin-when-cross-origin | Controls referrer info |
| Strict-Transport-Security | max-age=31536000 (prod only) | Forces HTTPS |

### Input Validation
- Email: regex validation + 255 char limit
- Password: 8-128 character range
- Name: 100 character limit
- Company name: 200 character limit
- Request body: 16MB max (`MAX_CONTENT_LENGTH`)

### Password Reset Flow
```
User → [Forgot Password Page] → POST /api/auth/forgot-password
                                        │
                                        ▼
                              Generate token_urlsafe(48)
                              Store in password_resets table
                              (expires in 1 hour, single-use)
                                        │
                                        ▼
                              Return reset link (demo mode)
                              [Production: send via email]
                                        │
                                        ▼
User → [Reset Password Page] → POST /api/auth/reset-password
                                        │
                                        ▼
                              Validate token (not expired, not used)
                              Hash new password (PBKDF2-SHA256)
                              Update users.password
                              Mark token as used
                                        │
                                        ▼
                              Redirect to login page
```

---

## Freemium Plan System

### Plan Configuration

| Feature | Free | Pro ($9/mo) | Premium ($19/mo) |
|---------|------|-------------|------------------|
| Application tracking | 5 max | Unlimited | Unlimited |
| AI Career Assistant | - | Yes | Yes |
| Advanced Analytics | - | Yes | Yes |
| CSV Export | - | Yes | Yes |
| Pipeline (Kanban) View | - | Yes | Yes |
| Contact Tracking | - | Yes | Yes |
| Priority Support | - | - | Yes |

### How Feature Gating Works

```
User clicks locked feature
        │
        ▼
Frontend calls API endpoint
        │
        ▼
@require_feature('ai_assistant') decorator checks plan
        │
        ├── Plan has feature → Allow request through
        │
        └── Plan missing feature → Return 403:
            {
              "error": "upgrade_required",
              "message": "This feature requires Pro or Premium...",
              "feature": "ai_assistant"
            }
                │
                ▼
        app.js API client intercepts error
                │
                ▼
        showUpgradeModal() → Branded modal with:
        - Lock icon + feature name
        - Upgrade message
        - "View Plans" button → /pricing
        - "Maybe Later" dismiss
```

### Billing Flow (Stripe-Ready)
- `/pricing` — Compare plans with feature matrix
- `/api/billing/checkout` — Creates payment (simulated; Stripe integration point marked in code)
- `/api/billing/downgrade` — Reverts to free plan
- `/billing` — Current plan, usage bar, payment history
- `/api/webhooks/stripe` — Webhook endpoint ready for Stripe events

---

## Admin Panel

### Access Control
- **First registered user** automatically becomes admin (`is_admin=True`)
- Admin nav section hidden by default, shown via JS when `user.is_admin` is true
- `@admin_required` decorator protects all admin routes
- Admins **bypass all plan limits** (unlimited apps, all features unlocked)

### Admin Dashboard (`/admin`)
- **4 KPI Cards**: Total Users, Total Revenue, Total Applications, Total Payments
- **Users by Plan**: Bar chart showing free/pro/premium distribution
- **Applications by Status**: Bar chart of global application statuses
- **Revenue Trend**: Monthly revenue chart
- **Recent Signups**: Table of latest user registrations
- **Top Users**: Leaderboard by application count

### User Management (`/admin/users`)
| Action | Description |
|--------|-------------|
| **Search** | Filter users by name or email |
| **Plan Filter** | Filter by free/pro/premium |
| **View Details** | Slide-out drawer with full user profile |
| **Change Plan** | Override user's plan (free/pro/premium) |
| **Block/Unblock** | Suspend user account (prevents login) |
| **Grant/Revoke Admin** | Toggle admin privileges |
| **Impersonate** | Login as any user for debugging (with banner + switch-back) |
| **Reset Password** | Admin can reset any user's password |
| **Delete User** | Permanently delete user + all their data (double confirmation) |

### Safety Guards
- Cannot remove your own admin access
- Cannot block yourself
- Cannot delete your own account
- Impersonation stores `real_admin_id` in session for safe switch-back

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account (first user → admin) |
| POST | `/api/auth/login` | Sign in |
| POST | `/api/auth/logout` | Sign out |
| GET | `/api/auth/me` | Get current user profile + plan |
| POST | `/api/auth/forgot-password` | Request password reset token |
| POST | `/api/auth/reset-password` | Set new password with token |
| POST | `/api/auth/change-password` | Change password (logged-in) |

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/applications` | List apps (filter: `status`, `search`, `sort`) |
| POST | `/api/applications` | Create application |
| GET | `/api/applications/:id` | Get app + timeline + contacts |
| PUT | `/api/applications/:id` | Update application |
| PATCH | `/api/applications/:id/status` | Quick status change |
| DELETE | `/api/applications/:id` | Delete application |
| POST | `/api/applications/:id/timeline` | Add timeline entry |
| POST | `/api/applications/:id/contacts` | Add contact (Pro+) |

### Stats & Export
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Dashboard stats + follow-ups |
| GET | `/api/export/csv` | Export applications as CSV (Pro+) |

### Billing
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plans` | Get all plan configurations |
| POST | `/api/billing/checkout` | Upgrade plan |
| POST | `/api/billing/downgrade` | Downgrade to free |
| GET | `/api/billing/history` | Payment history |
| POST | `/api/webhooks/stripe` | Stripe webhook receiver |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/stats` | Global analytics dashboard |
| GET | `/api/admin/users` | List users (search, plan filter) |
| GET | `/api/admin/users/:id` | User detail + apps + payments |
| PUT | `/api/admin/users/:id` | Update user fields |
| DELETE | `/api/admin/users/:id` | Delete user + all data |
| POST | `/api/admin/users/:id/set-plan` | Override user plan |
| POST | `/api/admin/users/:id/toggle-block` | Block/unblock user |
| POST | `/api/admin/users/:id/toggle-admin` | Grant/revoke admin |
| POST | `/api/admin/users/:id/impersonate` | Login as user |
| POST | `/api/admin/stop-impersonating` | Switch back to admin |
| POST | `/api/admin/users/:id/reset-password` | Reset user password |
| GET | `/api/admin/all-applications` | View all users' applications |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (DB connectivity test) |

---

## Local Development

### Prerequisites
- Python 3.9+
- pip

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Sandhoshsivan/hireflow-pro.git
cd hireflow-pro

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app (uses SQLite locally)
python app.py

# 5. Open browser
open http://127.0.0.1:5001
```

The first user to register automatically becomes the admin.

### Environment Variables (optional for local)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Flask session signing key |
| `DATABASE_URL` | _(empty = SQLite)_ | PostgreSQL connection string |
| `FLASK_ENV` | `development` | Set to `production` for secure cookies + HSTS |
| `PORT` | `5001` | Server port |

---

## Production Deployment

### Deploy to Render.com (Recommended)

#### Option A: One-Click Blueprint

1. Push code to GitHub
2. Go to [dashboard.render.com](https://dashboard.render.com)
3. Click **"New +"** → **"Blueprint"**
4. Connect your GitHub repo
5. Render reads `render.yaml` and auto-provisions:
   - Web service (Python, gunicorn)
   - PostgreSQL database (free tier)
   - Environment variables (SECRET_KEY auto-generated)
6. Deploy completes → you get a permanent URL like `https://hireflow-pro.onrender.com`

#### Option B: Manual Setup

1. **Create Web Service**:
   - Runtime: Python
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

2. **Create PostgreSQL Database** (free tier)

3. **Set Environment Variables**:
   ```
   FLASK_ENV=production
   SECRET_KEY=<generate random 64-char string>
   DATABASE_URL=<copy Internal Database URL from Render PostgreSQL>
   ```

4. Click Deploy

### How Dual Database Support Works

The app auto-detects the database engine at startup:

```python
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL:
    # PostgreSQL mode (production)
    # - Uses psycopg2 with RealDictCursor
    # - Fixes Render's postgres:// → postgresql:// prefix
    # - SQL uses %s placeholders, SERIAL, BOOLEAN, NOW(), TIMESTAMPTZ
else:
    # SQLite mode (local development)
    # - Uses sqlite3 with Row factory
    # - WAL journal mode + foreign keys enabled
    # - SQL uses ? placeholders, INTEGER, datetime('now')
```

All queries use `%s` placeholders. The SQLite driver auto-converts them to `?` internally. Helper functions (`now_sql()`, `month_sql()`, `date_sql()`) abstract dialect differences.

---

## How We Built It

### Phase 1: Core Application
Built the foundation — Flask app with SQLite, REST API for CRUD operations on job applications. Created the full UI design system in `main.css` with CSS custom properties (design tokens) for consistent theming across 40+ components. Built all pages: dashboard with KPIs, applications table with search/filter/sort, pipeline kanban board, analytics charts, and AI career assistant chat interface.

### Phase 2: Multi-User Authentication
Added user registration and login with secure password hashing (PBKDF2-SHA256). Introduced `user_id` foreign key so each user sees only their own data. Implemented session-based auth with Flask's signed cookies and `@login_required` decorator. Created the auth card UI with login, register, and forgot password pages.

### Phase 3: Freemium Monetization
Designed 3-tier plan system (Free/Pro/Premium) with a centralized `PLANS` configuration dict. Created `@require_feature()` decorator for backend enforcement that returns structured `upgrade_required` errors. Built a global upgrade modal in the frontend JS that intercepts 403 responses and shows a branded upgrade prompt. Added pricing comparison page with feature matrix, billing dashboard with usage tracking and payment history, and Stripe-ready checkout flow with webhook endpoint.

### Phase 4: Admin Panel
Built comprehensive admin dashboard with global analytics — 4 KPI cards, users-by-plan chart, applications-by-status chart, revenue trend, recent signups table, and top users leaderboard. Created full user management system with search, plan filtering, slide-out detail drawer, and admin actions: plan override, block/unblock, admin toggle, impersonation (with safe switch-back via `real_admin_id`), password reset, and user deletion with double confirmation. First registered user auto-becomes admin. Admins bypass all plan limits.

### Phase 5: Production Hardening
- Replaced SQLite-only database layer with dual PostgreSQL/SQLite driver abstraction
- Added password reset flow with cryptographically secure tokens (48-byte URL-safe, 1-hour expiry, single-use)
- Implemented IP-based rate limiting on login (10/5min), register (5/5min), and forgot-password (3/5min)
- Added security headers on all responses: X-Frame-Options, X-Content-Type-Options, XSS-Protection, Referrer-Policy, HSTS
- Upgraded password hashing to 260,000 PBKDF2 iterations with constant-time comparison via `secrets.compare_digest()`
- Added input validation with length limits (email 255, name 100, password 8-128, company 200) and request size cap (16MB)
- Secure session cookies: HttpOnly, SameSite=Lax, Secure in production, 7-day expiry
- Created custom 404/500 error pages with branded UI
- Added `/health` endpoint for uptime monitoring
- Set up structured logging with timestamps
- Created deployment configs: Procfile (gunicorn), render.yaml (IaC blueprint), requirements.txt, runtime.txt

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single-file backend** | Flask app small enough to keep in one file; avoids over-engineering for this scale |
| **No ORM** | Raw SQL gives full control over PostgreSQL/SQLite dialect differences and query optimization |
| **Vanilla JS (no framework)** | Zero bundle size, instant loads, no build step — keeps deployment simple |
| **Custom CSS (no Tailwind/Bootstrap)** | Full control over design, smaller payload, consistent design tokens system |
| **Server-rendered templates** | SEO-friendly, fast first paint, simple Jinja2 with progressive JS enhancement |
| **Cookie sessions** | Stateless server, no Redis needed, works perfectly for this scale |
| **In-memory rate limiting** | Simple and effective for single-process; can swap to Redis for multi-worker |
| **Dual DB driver** | SQLite for zero-config local dev, PostgreSQL for production reliability |

---

## License

MIT

---

Built with Flask + Claude AI
