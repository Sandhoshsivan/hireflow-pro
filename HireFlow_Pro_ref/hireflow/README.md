# HireFlow Pro — Job Application Tracker

A full-stack, multi-page job tracking app with SQLite database, REST API backend, and AI assistant.

## Tech Stack
- **Backend**: Python (Flask) + SQLite3
- **Frontend**: Jinja2 templates + Vanilla JS + Custom CSS (light theme)
- **AI**: Claude claude-sonnet-4-20250514 via Anthropic API

## Setup & Run

### 1. Install Python dependencies
```bash
pip install flask
```

### 2. Run the app
```bash
python app.py
```

### 3. Open browser
```
http://127.0.0.1:5000
```

That's it! The SQLite database (`hireflow.db`) is created automatically with demo data on first run.

## Pages
| URL | Description |
|-----|-------------|
| `/dashboard` | KPIs, funnel chart, response rate, recent apps |
| `/pipeline` | Kanban board view (Saved → Applied → Interview → Offer → Rejected) |
| `/applications` | Full table with search, filter, sort + detail drawer |
| `/analytics` | Charts: status breakdown, sources, monthly trend, priority + AI insights |
| `/ai-assistant` | Chat with Claude — knows your profile + real job data |
| `/api/export/csv` | Download all applications as CSV |

## API Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/applications` | List applications (filter, search, sort) |
| POST | `/api/applications` | Create application |
| GET | `/api/applications/:id` | Get single application with timeline |
| PUT | `/api/applications/:id` | Update application |
| PATCH | `/api/applications/:id/status` | Quick status update |
| DELETE | `/api/applications/:id` | Delete application |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/export/csv` | Export all as CSV |

## Database Schema
- **applications** — main table with all job details
- **timeline** — event log per application (auto-updated on status change)
- **contacts** — recruiter/contact info per application

## Features
- ✅ Full CRUD for applications
- ✅ Auto-ghost: marks Applied → Ghosted after 14 days
- ✅ Follow-up reminders (date-based alerts in sidebar + dashboard)
- ✅ Timeline tracking (every status change logged automatically)
- ✅ Kanban pipeline view
- ✅ Analytics with bar charts and AI insights
- ✅ AI assistant powered by Claude (knows your .NET background)
- ✅ CSV export
- ✅ Light theme, clean professional UI
