# Code Clash Offline LAN Contest Sync Specification

This document provides the complete API specification, payload structure, security authentication, and sample code to connect your offline LAN-based contest server with the online E-Code platform.

---

## 1. Overview & Architecture

```
┌─────────────────────────────────┐               ┌──────────────────────────────────────┐
│  Offline University LAN Server  │               │      Online E-Code Web Platform      │
│      (Code Clash Engine)        │               │           (Cloud Backend)            │
│                                 │               │                                      │
│  - Hosted locally on LAN        │               │  - Firestore Database                │
│  - Zero internet during contest │               │  - Batch-based Leaderboards          │
│  - Contests & score computation │  HTTP POST    │  - Verified Student Profiles         │
│  - At contest finish:           ├──────────────►│  - Live Public Dashboards            │
│    Pings online E-Code API      │  /codeclash/  │                                      │
│    with results payload         │     sync      │                                      │
└─────────────────────────────────┘               └──────────────────────────────────────┘
```

When a contest finishes on your local LAN network, the LAN server connects to the internet and pushes the final contest results to E-Code. E-Code automatically:
1. Stores the official contest record and contest-specific standings.
2. Links every participant to their verified student account using their unique **`enrollmentNumber`**.
3. Updates the **Batch-Based Leaderboards** (`2024`, `2025`, `2026`, etc.).
4. Updates the **All-Time Global Leaderboard**.
5. Appends the event to `admin_logs` for an audit trail.

---

## 2. Security & Authentication

To ensure no unauthorized entity can forge or tamper with contest results or download student rosters, both the Roster Export and Sync endpoints enforce secret-key authentication.

### Option A: Sync Secret Header (Recommended for LAN scripts)
In your `backend/.env` file, configure:
```dotenv
CODECLASH_SYNC_SECRET=codeclash_lan_super_secret_key_2026
```

Your LAN server must supply this key in one of these headers:
```http
X-CodeClash-Sync-Secret: codeclash_lan_super_secret_key_2026
```
*(Or `X-Sync-Secret: codeclash_lan_super_secret_key_2026`)*

### Option B: Superadmin Bearer Token
If calling from an admin script with a logged-in Superadmin account:
```http
Authorization: Bearer <SUPERADMIN_FIREBASE_JWT_TOKEN>
```

Any request without a matching secret or Superadmin token is immediately rejected with `HTTP 401 Unauthorized`.

---

## 3. Pre-Contest: Roster Export & Offline Authentication

Before the contest begins (while your LAN server laptop is connected to the internet), fetch the authorized student roster. Each student on E-Code has a unique **6-digit Contest PIN** visible in their profile.

* **Endpoint:** `GET /api/v1/codeclash/roster`
* **Header:** `X-CodeClash-Sync-Secret: <YOUR_SECRET>`

### Successful Response (HTTP 200 OK)

```json
{
  "success": true,
  "message": "Student roster exported successfully for offline LAN server",
  "data": {
    "totalStudents": 45,
    "exportedAt": "2026-11-22T10:05:00.000Z",
    "roster": [
      {
        "enrollmentNumber": "U2451001",
        "username": "alex_coder",
        "fullName": "Alex Johnson",
        "batchYear": "2024",
        "contestPin": "749201"
      },
      {
        "enrollmentNumber": "U2561011",
        "username": "riya_dev",
        "fullName": "Riya Sharma",
        "batchYear": "2025",
        "contestPin": "382910"
      }
    ]
  }
}
```

### How to Authenticate Students Offline on the LAN:
1. Save the downloaded roster into a local JSON file or SQLite database on the LAN server: `contestants.json`.
2. When students sit at their lab computers:
   - They enter their **Enrollment Number** (`U2451001`) and their **6-digit Contest PIN** (`749201`).
   - The offline LAN server checks if the enrollment number exists and if the PIN matches.
   - If verified, the student is logged in with zero internet needed!

---

## 4. Post-Contest: Sync Endpoint Specification

* **Endpoint:** `POST /api/v1/codeclash/sync`
* **Content-Type:** `application/json`

### Request Body (JSON Schema)

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `contestId` | string | **Yes** | Unique identifier (e.g., `cc_2026_spring_01`, `round-1-algo`). |
| `title` | string | **Yes** | Human-readable contest title (e.g., `Code Clash 2026 - Round 1`). |
| `description` | string | No | Short overview or problem topic list. |
| `startTime` | string (ISO 8601) | **Yes** | Contest start time (e.g., `2026-11-22T10:00:00Z`). |
| `endTime` | string (ISO 8601) | **Yes** | Contest finish time (e.g., `2026-11-22T12:00:00Z`). |
| `durationMinutes` | number | **Yes** | Contest length in minutes (e.g., `120`). |
| `totalProblems` | number | **Yes** | Number of algorithmic problems in the contest. |
| `batchTarget` | string | No | `ALL` or specific targeted batch like `2025`. |
| `problems` | array | No | Metadata for each problem (ID, title, max points). |
| `participants` | array | **Yes** | List of all participants and their final scores (ordered by rank). |

#### Participant Object:
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `rank` | number | **Yes** | Official contest rank (`1`, `2`, `3`...). |
| `enrollmentNumber`| string | **Yes** | **Crucial:** Student's college enrollment number (e.g. `U2451001`). Matches their E-Code profile. |
| `username` | string | **Yes** | Handle used during the contest. |
| `fullName` | string | **Yes** | Student's full name. |
| `batchYear` | string | No | Academic batch year (`2024`, `2025`, `2026`). If omitted, inferred automatically from enrollment number. |
| `score` | number | **Yes** | Total points scored in the contest. |
| `problemsSolved` | number | **Yes** | Count of accepted (AC) problems. |
| `timePenaltyMinutes`| number | No | Penalty/finish time for tie-breaking. |
| `solvedProblems` | string[] | No | Problem IDs solved by the participant (e.g. `["A", "C", "D"]`). |

---

### Example JSON Payload

```json
{
  "contestId": "codeclash-2026-spring-01",
  "title": "Code Clash 2026: Algorithm Sprint #1",
  "description": "2-hour speed coding contest covering Arrays, Graphs, Dynamic Programming, and Bit Manipulation.",
  "startTime": "2026-11-22T10:00:00.000Z",
  "endTime": "2026-11-22T12:00:00.000Z",
  "durationMinutes": 120,
  "totalProblems": 4,
  "batchTarget": "ALL",
  "problems": [
    { "problemId": "A", "title": "Subarray Maximum XOR", "maxPoints": 100 },
    { "problemId": "B", "title": "Shortest Path in Weighted DAG", "maxPoints": 150 },
    { "problemId": "C", "title": "Grid Traversal with Obstacles", "maxPoints": 200 },
    { "problemId": "D", "title": "String Permutations with Constraints", "maxPoints": 250 }
  ],
  "participants": [
    {
      "rank": 1,
      "enrollmentNumber": "U2451001",
      "username": "alex_coder",
      "fullName": "Alex Johnson",
      "batchYear": "2024",
      "score": 600,
      "problemsSolved": 4,
      "timePenaltyMinutes": 68,
      "solvedProblems": ["A", "B", "C", "D"]
    },
    {
      "rank": 2,
      "enrollmentNumber": "U2561011",
      "username": "riya_dev",
      "fullName": "Riya Sharma",
      "batchYear": "2025",
      "score": 450,
      "problemsSolved": 3,
      "timePenaltyMinutes": 75,
      "solvedProblems": ["A", "B", "C"]
    },
    {
      "rank": 3,
      "enrollmentNumber": "U2451042",
      "username": "priya_algo",
      "fullName": "Priya Verma",
      "batchYear": "2024",
      "score": 250,
      "problemsSolved": 2,
      "timePenaltyMinutes": 45,
      "solvedProblems": ["A", "B"]
    }
  ]
}
```

---

### Successful Response (HTTP 200 OK)

```json
{
  "success": true,
  "message": "Code Clash LAN contest results synchronized successfully",
  "data": {
    "contestId": "codeclash-2026-spring-01",
    "participantsSynced": 3,
    "batchesUpdated": ["2024", "2025", "all"]
  }
}
```

---

## 5. Ready-to-Use LAN Server Scripts

### Script 1: Fetch Student Roster Before Contest (`fetch_roster.py`)
Run this on your laptop before entering the offline lab to download all registered students, usernames, enrollment numbers, and 6-digit Contest PINs:

```python
import requests
import json

ECODE_API_URL = "http://localhost:5000/api/v1/codeclash/roster"  # Your online backend URL
SYNC_SECRET = "codeclash_lan_super_secret_key_2026"

headers = {
    "X-CodeClash-Sync-Secret": SYNC_SECRET
}

print("[INFO] Fetching student roster from E-Code...")
response = requests.get(ECODE_API_URL, headers=headers)

if response.status_code == 200:
    data = response.json()
    roster = data["data"]["roster"]
    print(f"[SUCCESS] Downloaded {len(roster)} authorized students.")
    
    # Save locally to offline database or JSON file
    with open("offline_roster.json", "w") as f:
        json.dump(roster, f, indent=2)
    print("[SUCCESS] Roster saved to offline_roster.json for local LAN authentication.")
else:
    print(f"[ERROR {response.status_code}] Failed to download roster:", response.text)
```

### Script 2: Push Contest Results After Contest (`sync_to_ecode.py`)
Run this on your LAN server after the contest ends:

```python
import requests
import json

ECODE_API_URL = "http://localhost:5000/api/v1/codeclash/sync"  # Replace with your deployed API URL
SYNC_SECRET = "codeclash_lan_super_secret_key_2026"           # Matches CODECLASH_SYNC_SECRET in .env

contest_payload = {
    "contestId": "codeclash-round-01",
    "title": "Code Clash LAN Championship Round 1",
    "description": "Offline LAN tournament hosted at JKIAPT Computer Center.",
    "startTime": "2026-11-22T10:00:00Z",
    "endTime": "2026-11-22T12:00:00Z",
    "durationMinutes": 120,
    "totalProblems": 4,
    "batchTarget": "ALL",
    "problems": [
        {"problemId": "A", "title": "Prefix Sum Queries", "maxPoints": 100},
        {"problemId": "B", "title": "Tree Diameter", "maxPoints": 150},
        {"problemId": "C", "title": "Knapsack Variation", "maxPoints": 200},
        {"problemId": "D", "title": "Flow Network", "maxPoints": 250}
    ],
    "participants": [
        {
            "rank": 1,
            "enrollmentNumber": "U2451001",
            "username": "alex_johnson",
            "fullName": "Alex Johnson",
            "batchYear": "2024",
            "score": 600,
            "problemsSolved": 4,
            "timePenaltyMinutes": 62,
            "solvedProblems": ["A", "B", "C", "D"]
        }
    ]
}

headers = {
    "Content-Type": "application/json",
    "X-CodeClash-Sync-Secret": SYNC_SECRET
}

response = requests.post(ECODE_API_URL, headers=headers, json=contest_payload)

if response.status_code == 200:
    print("[SUCCESS] Contest results synced with E-Code:", response.json())
else:
    print(f"[ERROR {response.status_code}] Failed to sync:", response.text)
```

### Node.js Script (`sync.js`)

```javascript
const ECODE_API_URL = 'http://localhost:5000/api/v1/codeclash/sync';
const SYNC_SECRET = 'codeclash_lan_super_secret_key_2026';

async function syncContest(payload) {
  const response = await fetch(ECODE_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CodeClash-Sync-Secret': SYNC_SECRET,
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (response.ok) {
    console.log('Synced successfully:', data);
  } else {
    console.error('Sync failed:', data);
  }
}
```

### cURL Command

```bash
curl -X POST "http://localhost:5000/api/v1/codeclash/sync" \
  -H "Content-Type: application/json" \
  -H "X-CodeClash-Sync-Secret: codeclash_lan_super_secret_key_2026" \
  -d @contest_results.json
```

---

## 5. Public Leaderboard Query APIs

Anyone on the frontend or external clients can query these endpoints to view leaderboards:

### A. Batch-Based Leaderboards
* **Endpoint:** `GET /api/v1/codeclash/leaderboards?batch=2024`
* **Query Parameters:**
  * `batch`: Filter by year (`2024`, `2025`, `2026`, or `all` for cumulative global standings).
  * `page`: Page number (default: `1`).
  * `limit`: Results per page (default: `50`).

### B. List Available Batches
* **Endpoint:** `GET /api/v1/codeclash/leaderboards/batches`
* **Returns:** `["all", "2024", "2025", "2026"]`

### C. Contest-Specific Standings
* **Endpoint:** `GET /api/v1/codeclash/leaderboards/contests/:contestId`
* **Returns:** Standings for that specific round.
