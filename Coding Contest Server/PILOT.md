# Running the contest site on the Acer

Open the [contest homepage](http://127.0.0.1:8765/) on the laptop. All website pages belong to one React project in `frontend/`. Django, its database, compilers and services live in `backend/`.

## Candidate journey

1. Open **Create account**. Enter a full name, enrollment number, email, phone, username and password. A JPEG, PNG or WebP profile picture is optional. Uploaded pictures are resized and re-encoded. A candidate can update contact information and their picture from their profile.
2. Choose a live event on the homepage. Upcoming events show their start and end times. Entering a live event creates its roster entry. Public registration always creates an ordinary candidate account.
3. Select Python, C++17 or Java 21. The editor supplies the problem’s function declaration. Write the function body and return a value. The server supplies standard imports, a solution wrapper and the test driver. The C++ and Java compilers run once per job, then each case gets a fresh isolated process. Numeric `int` arguments in the compiled-language pilot use signed 32-bit values. Core signature types are integers, booleans, strings and arrays of these types.
4. Choose **Run tests** for samples and saved cases, or **Submit solution** for the official suite. Official judging stops at the first failure and shows that case and the number of tests skipped. Code drafts are tracked separately per language. A failed hidden case can be saved with **Add to My Tests**. Official solves and times appear on the [practice leaderboard](http://127.0.0.1:8765/leaderboard/1/).
5. **Sign out** ends the local Django session and opens the signed-out page. A wrong username/password combination returns the same generic error regardless of which account exists.

## Organizer journey

Use the shared [sign-in page](http://127.0.0.1:8765/login/). A staff account lands in [Contest control](http://127.0.0.1:8765/organizer/). The organizer is provisioned locally. The public signup form cannot grant staff access.

- **Schedule contest** sets its title and start/end using the organizer's local time. Use the contest selector to switch the dashboard.
- **Participants** shows registrations for the selected contest, workspace presence, enrollment numbers, last contact and official submission counts. Eligibility changes require an organizer and a reason.
- **Connection events** shows when a participant opened the workspace, when its heartbeat expired, and when it resumed. The workspace checks in every 10 seconds. After more than 45 seconds without a heartbeat, the observer records an incident and the open dashboard displays an alert. Totals refresh every four seconds. Closing a browser tab, device sleep and network loss can all produce the same signal. Physical AP association is a separate observation.
- **Problems** lets an organizer publish a statement, Python starter and typed function signature. Add each test's positional arguments as a JSON list, supply its expected return value and mark visible examples. For a single integer-list parameter, use arguments such as `[[2,5,8]]` and return value `2`. The same signature generates the Java/C++ starters.
- **Submissions** lists recent official and archive results. Expand a row to inspect its source. **Standings** opens the projector and exposes the JSON download after finalization.

To view the original organizer and demo sign-ins privately on the laptop:

```bash
cd "$HOME/Launchpad/Coding Contest LAN/Coding Contest Server/backend"
cat var/pilot-logins
```

To provision another organizer from the backend:

```bash
export LD_LIBRARY_PATH="$PWD/var/maria-runtime/usr/lib/x86_64-linux-gnu"
.venv/bin/python manage.py createsuperuser
```

## Processes and storage

```bash
cd "$HOME/Launchpad/Coding Contest LAN/Coding Contest Server/backend"
./scripts/server status
./scripts/server start
```

Use `./scripts/server stop` to stop the pilot. Four user systemd units run the web server, database, judge and presence observer. Their names start with `coding-contest-pilot-` and end in `web`, `db`, `judge` and `presence`. Inspect a service using `journalctl --user -u SERVICE -n 50`.

MariaDB stores contest data in `backend/var/maria-data/` and listens on a private Unix socket. The judge uses one execution slot. GCC and OpenJDK are staged under `backend/var/toolchain/`. Compiled jobs run in disposable Linux namespaces within memory-, process- and time-limited systemd units. Runtime dependencies and browser assets are stored locally. Keep the private runtime directory and credentials out of public releases.

## Closing and archive

During the contest, drafts checkpoint to MariaDB. **Synced** confirms receipt of the last edit. After the deadline, the worker captures each available final draft per participant, problem and language. It evaluates unfinished, incorrect and accepted sources, preserving the source even when compilation fails. A browser's unsynced changes can only be recovered from that device. Official submissions have priority and determine the final leaderboard. Once the in-time official jobs have resolved, the final public JSON snapshot is stored separately in MariaDB. An infrastructure error needs organizer attention before those results can finalize.

## Development

| Folder | Contents |
|---|---|
| `frontend/src/` | React homepage, auth/profile, organizer control, workspace, leaderboard, styles |
| `frontend/templates/` | Single HTML shell |
| `frontend/dist/` | Locally served production bundle |
| `backend/contest/` | Django settings, routes and WSGI entry point |
| `backend/arena/` | Models, API, migrations, presence observer, sandbox, compilers and judging |
| `backend/scripts/` | Database initialization and service control |
| `backend/var/` | Private persistent database, keys, tools and collected assets |

Rebuild and serve frontend changes with the installed dependencies:

```bash
cd "$HOME/Launchpad/Coding Contest LAN/Coding Contest Server"
node frontend/build.mjs
cd backend
./scripts/init.sh
systemctl --user restart coding-contest-pilot-web
CONTEST_TEST_SQLITE=1 .venv/bin/python manage.py test arena
```

The site currently binds to the Acer’s loopback address. Deployment to the dual-band LAN, trusted HTTPS, and a full-size contest rehearsal remain separate rollout steps.
