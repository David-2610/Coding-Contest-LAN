# Code Clash 1.0 — Offline LAN Competitive Programming Platform

Code Clash 1.0 is an offline-first competitive programming contest platform designed to run in air-gapped or closed Local Area Networks (LAN) on a Linux host machine, with cloud synchronization to **E-Code** (`https://ecode-backend.onrender.com`).

---

## 🔒 Security & Data Privacy

To protect organizer credentials, student identities, PINs, and code submissions:
- **Organizer Passwords & Auth Keys:** Stored in `backend/var/` and database files which are excluded from Git via `.gitignore`.
- **Student Authentication:** Students authenticate offline using their E-Code enrollment number and 6-digit PIN. PINs are salted and hashed with Django's PBKDF2 algorithm in the local MariaDB database.
- **Participant Submissions:** Staged inside private local database tables and disposable Linux execution namespaces. They are never committed to version control.
- **Git Exclusions:** The root `.gitignore` protects all keys (`*.key`), local SQLite/MariaDB storage (`var/maria-data`, `*.sqlite3`), local toolchains, and exported result JSONs (`sync-payload*.json`).

---

## 📁 Repository Structure

```
├── Coding Contest Server/
│   ├── backend/
│   │   ├── arena/                # Core Django app: models, engine, judges, API endpoints
│   │   │   ├── ecode_client.py   # Cloud integration client for E-Code API
│   │   │   ├── ecode_contest.py  # Contest schema, timezone & payload builder
│   │   │   ├── portal.py         # Organizer & candidate API endpoints
│   │   │   ├── engine.py         # Local judge execution and scoring engine
│   │   │   └── management/       # Commands: fetch contest, import roster, sync, worker
│   │   ├── contest/              # Django settings, WSGI, URLs
│   │   ├── scripts/              # Service controller (`scripts/server`)
│   │   └── var/                  # [GIT-IGNORED] MariaDB runtime, keys, cached banners
│   └── frontend/
│       ├── src/                  # React & CodeMirror 6 UI (Workspace, Organizer, Lobby)
│       ├── dist/                 # Bundled production assets & schemas
│       └── build.mjs             # esbuild bundling script
└── LAN Server/
    └── service/                  # Dual-band Wi-Fi access point, dnsmasq, and nftables scripts
```

---

## 🚀 Quick Start Guide

### 1. Environment Configuration

Create a `.env` file (or provide environment variables to the backend service):

```env
ECODE_API_BASE_URL=https://ecode-backend.onrender.com
CONTEST_TIMEZONE=Asia/Kolkata
CODECLASH_SYNC_SECRET=<YOUR_ECODE_SYNC_SECRET>
```

*(Note: If `CODECLASH_SYNC_SECRET` is not set in `.env`, the server automatically reads from `backend/var/ecode-sync.key`)*.

---

### 2. Starting Local Services

From `Coding Contest Server/backend`:

```bash
# Check service status
./scripts/server status

# Start all local services (Database, Web Server, Judge Worker, Presence Observer)
./scripts/server start
```

The contest interface will be accessible at:
- **Organizer Dashboard:** `http://127.0.0.1:8765/organizer/`
- **Contestant Lobby:** `http://127.0.0.1:8765/` (or via LAN network `http://codeclash.test/`)

---

### 3. Contest Workflow

1. **Fetch Active Contest from E-Code:**
   - In the web dashboard, open the **E-Code Cloud** tab and click **Fetch Active Contest from E-Code**.
   - Or run CLI:
     ```bash
     .venv/bin/python manage.py fetch_ecode_contest
     ```
2. **Synchronize Student Roster:**
   - Open `/roster/` in the dashboard and click **Refresh roster from E-Code**.
   - Or run CLI:
     ```bash
     .venv/bin/python manage.py import_ecode
     ```
3. **Add Questions:**
   - In the **Problems** tab, click **Add problem** and select a single JSON or an array of multiple questions `[...]`.
   - Or use batch import CLI:
     ```bash
     .venv/bin/python manage.py import_problem <CONTEST_ID> /path/to/problems/ --replace
     ```
4. **Conduct Contest Offline:**
   - Disconnect internet. Candidates connect to contest Wi-Fi and login with their E-Code enrollment number and 6-digit PIN.
   - Code evaluation and scoreboard updates execute 100% locally.
5. **Post-Contest Cloud Synchronization:**
   - Reconnect to internet.
   - Go to **E-Code Cloud** -> **Preview Sync Payload** -> **Send final leaderboard to E-Code**.
