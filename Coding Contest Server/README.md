# CodeClash 1.0

[Current setup, authentication, question imports and LAN instructions](OPERATIONS.md)

<details><summary>Historical pilot documentation (superseded)</summary>

# Coding Contest Server

[Open the running local pilot and operating guide](PILOT.md). The working site is organized into two folders. **frontend/** owns the unified React schedule, registration, sign-in, contestant editor, organizer control and projector. **backend/** owns authentication and staff provisioning, MariaDB, the observer and Python/C++/Java judging. The staged local implementation uses esbuild and a private function-judging adapter. References to Vite and DOMjudge below describe earlier design candidates. The operator guide documents the running implementation.

**Architecture for the first implementation.** One offline web application on the Acer serves three audiences: contestants writing solutions, organizers managing the contest, and spectators watching the projector. Both contest Wi-Fi bands lead to the same application. The first prototype should prove the failed-test workflow before work begins on the full dashboard.

## Selected architecture for the Acer

Use a Python/Django backend, a prebuilt React and TypeScript contestant workspace with CodeMirror, one local MariaDB instance, and one isolated judging worker. The Acer has an Intel Core i7-13620H and roughly 14 GiB of usable RAM. Build frontend assets before the contest. Each contestant’s browser runs the editor, and the Acer serves its files. The live deployment requires no frontend development server or external APIs. This is a load-conscious starting point; capacity still needs a rehearsal.

Queue both practice and official submissions. Use one execution slot shared between them. At each job boundary, take the oldest official submission first, then a practice run when the official queue is empty. Show queue state and limit outstanding practice runs per contestant. Count the server receipt time for scoring even when judging is delayed. During rehearsal, record peak memory, CPU temperature, and queue wait and execution times separately before raising concurrency.

**Editor acceptance test.** Opening a new problem in Python displays the supplied function signature and an editable body. The contestant can solve it without writing an input parser, output formatter or main program. Switching to C++ opens the equivalent typed starter; switching back restores the Python draft. Pressing Run exercises the same function with public or saved inputs. Submit evaluates it against the published official suite. After a failed case, Add to My Tests must reproduce the failure using the same arguments and comparison rules.

## Frameworks and ownership

| Component | Proposed choice | Responsibility |
|---|---|---|
| Contest application | Python and Django 5.2 LTS for the API and organizer tools | Local accounts, enrollment, roles, problem authoring, contest clock, submissions, eligibility and the leaderboard JSON API. Use Django admin for initial roster entry and purpose-built screens for contest operations. [Django overview](https://docs.djangoproject.com/en/5.2/intro/overview/) |
| Contestant interface | React and TypeScript, built with Vite | Coordinate the problem, language-specific starter, editor, test tabs and submission feedback. Serve the compiled assets locally. [React components](https://react.dev/learn/thinking-in-react) · [Vite deployment](https://vite.dev/guide/static-deploy.html) |
| Editor | CodeMirror 6, bundled on the Acer | Edit source, switch languages, show sample tests and failed cases, and keep the editor usable during a Wi-Fi interruption. |
| Browser storage | IndexedDB | Save drafts and “My Tests” under the signed-in account, contest, problem and problem revision. Clear or offer to remove local data on shared-device sign-out. [IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API) |
| Database | Local MariaDB, separate databases and accounts for Django and DOMjudge | Django owns contest records and display rules. DOMjudge owns judging records. Exchange IDs and verdicts through a server-side adapter. |
| Judging | Self-hosted DOMjudge and one isolated judge worker for the pilot | Run local Python and C++ toolchains with resource limits. Validate one language first. Restrict the worker’s view of files and network, including the expected answers and web/database credentials. [DOMjudge manual](https://www.domjudge.org/docs/manual/index.html) |
| Hosting | Local reverse proxy, Gunicorn, systemd | Serve the web app and bundled assets on the contest LAN. Keep judge, database and organizer controls on private listeners. Prepare pinned packages, compilers and assets before contest day. |

## Why this split

Django supplies local authentication, permissions, database migrations and a staff admin. These reduce the work needed for roster management and problem authoring. React suits the interactive contestant workspace. Node.js is the JavaScript runtime used by the proposed frontend build tools. It could also host the contest API with a framework such as Fastify, in which case the project would need to select and integrate authentication, migrations and an organizer interface. Both approaches can run entirely on the LAN. Django plus React is the proposed default. Contestant language support is independent of the web backend. [Django admin](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/) · [Node.js overview](https://nodejs.org/en/learn/getting-started/introduction-to-nodejs)

## Function-based problems

The organizer defines a function name, ordered parameter names and types, return type, and three sample argument/expected-return pairs. Store the signature with the problem revision. Generate matching starter functions and judge drivers for each supported language. The pilot supports integers, strings, booleans and lists of these types. Define integer ranges and comparison rules per problem. Contestants fill in the function body once and reuse it for every sample, saved case and official test. Keep a separate draft per problem revision and language.

For example, a problem can supply Python's `def count_even(nums: list[int]) -> int:` or a C++ function accepting a vector of integers. With the input list [2, 5, 8], the expected return value is 2. The contestant writes the counting logic. A language-specific driver converts one case's arguments to native values, calls the function and serializes the return value. The judge compares the result against the expected value outside the contestant's process. Keep expected answers, other hidden inputs and credentials out of the execution environment. Treat debug prints separately from the returned result. Compile once where appropriate and run each case with fresh state and enforced limits. A modified or missing signature should produce a clear diagnostic.

Use the same versioned driver and comparison rules for **Run** and **Submit**. A failed case saved to **My Tests** carries the typed arguments and expected value, so the contestant can replay it directly. Verify both languages against identical fixtures and prototype how the driver is packaged with submitted code for the chosen judge.

## Request flow

```text
Contestant browser ──┐
                     ├── contest.test ── local proxy ── Django ── application database
Projector browser ───┘                                     │
Organizer on Acer ── organizer-only listener ──────────────┤
                                                          ├── judging adapter ── DOMjudge ── isolated worker
Read-only AP observer ── timestamped radio events ─────────┘
```

The adjacent LAN Server project owns the radios, DHCP, DNS, bridge and firewall. The platform owns the pages and contest data. Stage it on loopback first. At cutover, coordinate the existing port-80 page service and its hard-coded health probe with the proxy. Preserve a local health route and test startup, confirmation and rollback with both bands. For authenticated sessions, plan local HTTPS with a certificate trusted on participant devices and explicitly allow its port on the contest bridge.

## What a contestant does

1. Signs in locally. Their profile shows name and enrollment number. The projector uses a separate display name.
2. Opens a problem with a statement, input/output format, constraints and three visible examples. The editor stores drafts locally.
3. Selects **Run** to execute samples or saved cases. Practice results are private and have no effect on standings.
4. Selects **Submit** to run the official suite against a fixed problem revision. Record receipt on the server and return a submission ID immediately. A retry of the same request reuses that ID. Submissions arriving within contest time can finish judging after the deadline.
5. An official submission stops at its first failure. Show the number of skipped cases. For a failed hidden case, show that contestant the input, expected output and actual output or execution error. **Add to My Tests** saves a private browser copy for the same problem. Passed hidden cases stay server-side. A compile failure or infrastructure error identifies which cases were unrun. An interrupted evaluation stays pending or is retried before scoring.

The API authorizes every case disclosure against the signed-in owner, submission, problem revision and recorded failed verdict. Clearly mark truncated output. Private cases and source code never travel through the public standings endpoint.

## Admin workflow

- **Roster and check-in.** Create/import contestants, enforce unique enrollment numbers within a contest, and associate a checked-in device with an account for incident review.
- **Question authoring.** Draft the statement, constraints, language limits and input/output rules. Add sample and hidden input/expected-output pairs manually or in bulk. Verify a reference solution and a deliberately flawed solution, preview the contestant view, then publish a versioned problem package. A correction creates a new revision and an explicit rejudge decision. [DOMjudge package import](https://www.domjudge.org/docs/manual/9.0/import.html)
- **Live operations.** Inspect the queue, submissions, case verdicts, standings and judge health. Only organizers can see every participant’s results.
- **Connection incidents.** A separate read-only observer records association and disconnect events from both radios. Correlate band switches and mark observer gaps as unknown. A device departure is evidence for review. Disqualification and reinstatement require a human decision with operator, time and reason. Preserve the record and recalculate eligibility for standings.

## Scoring and projector API

Each problem earns one solve on its first fully accepted official submission. Rank eligible contestants by solves descending, then total solve time ascending. Sum the elapsed time from contest start to the server receipt of each first accepted solution. Equal totals share rank. Wrong attempts carry zero time penalty. Practice runs never enter that calculation.

Example: A finishes problems at minutes 12 and 30. B finishes at minutes 18 and 28. Both have two solves. A ranks ahead with 42 minutes against 46. A contestant with three solves ranks above both.

Provide a read-only local endpoint, `GET /api/contests/{id}/leaderboard`. Return contest state, snapshot timestamp, rank, public display name, number solved, total solve time and per-problem solve times. Start with five-second polling and a visible last-updated time if connectivity drops. Use the same scoring function for admin and public views, with publication and eligibility rules applied on the server. If a freeze is enabled, serve the published snapshot to spectators. A disqualification or rejudge retains an audit trail.

## Final results and submission storage

**Archive at the deadline.** For every contestant, collect the latest authored editor contents for each problem and language they worked on, including unsubmitted, incomplete, accepted and failing code. Preserve earlier officially submitted versions as well, with their original verdicts and receipt times. Mark untouched starters as unattempted. If identical source appears as a final draft and an official submission, keep both associations and store the source once.

**Capture before closing.** Browser-only drafts can be lost if a contestant disconnects or closes the tab. During the contest, retain a local browser draft and debounce private recovery checkpoints to the Acer. Confirm receipt with a revision number and show the contestant whether their changes have synced. Keep the latest acknowledged in-time revision durably staged per editor. This temporary staging supports the end-of-contest collection; the permanent archive is created at closing. Freeze editing at the server deadline. Use the latest in-time server checkpoint if the browser is unreachable and label the snapshot with its last sync time. A final unsynced edit on a disconnected device cannot be guaranteed. Any later recovery is separately labeled for organizer review.

**Close and queue.** Close new official submissions, freeze the in-time draft revisions, and durably record a finalization job. Copy frozen sources to the private local MariaDB archive in bounded batches. For each archived version, record a unique work item in the same transaction that saves its source. Finish pending official submissions first. One isolated worker then compiles or loads and runs each final draft against its problem revision with time, memory and output limits. Reuse a completed verdict only for an identical source, language, toolchain and test revision. Record accepted, wrong answer, compile error, runtime error, timeout or infrastructure failure alongside the original source. Retry interrupted work with bounded retries and deduplication, expose progress and unresolved errors to the organizer, and retain the source for every outcome.

**Scoring and export.** Automatic end-of-contest checks are marked as archive evaluations. The proposed scoring default continues to count only in-time official submissions. Once all such submissions have resolved, save the immutable leaderboard JSON in MariaDB; draft evaluation can continue independently. Resume both operations after restart. Require one snapshot per contest and revision. Organizer-approved corrections create a new revision with its reason and preserve the original.

Store the schema version, contest ID, contest end time, generation time, revision, scoring rules and ordered rows. Each row contains public display name, rank, solves, total solve time and per-problem solve times with explicit units. An organizer can download any finalized revision as a UTF-8 JSON file. Export the stored snapshot directly so later roster edits or scoreboard changes cannot silently alter a historical export. Enrollment numbers and submitted source remain outside the public results file.

**Acceptance test.** End a contest with an accepted submission, a wrong submission, an unsubmitted working draft and an unfinished draft containing a syntax error. Disconnect one browser after a checkpoint and interrupt the worker during finalization. Verify every available in-time source is preserved exactly, each final draft receives an outcome or a visible infrastructure error, retries create no duplicate archive records, and the exported leaderboard contains only official results and no source code.

## Handling a deadline burst

Start the rehearsal with two Gunicorn web workers on the Acer and one isolated execution slot. Each web worker can accept requests independently. Keep sessions, source checkpoints, submission receipts and pending jobs in shared local MariaDB storage. In a short transaction, apply the server-side admission deadline, persist the source and its job, and commit before acknowledging. Give each official submission a client-generated idempotency key scoped to contestant and contest. A retry after a lost reply returns the original receipt even after closing. A new late request cannot claim an earlier time from its client clock. Use monotonic draft revision numbers per editor so an older checkpoint cannot overwrite a newer one. [Gunicorn worker model](https://gunicorn.org/design/)

The browser submits incrementally during the contest. At closing the server freezes the revisions it already holds and queues archive work in batches. Web requests never wait for compilation. Cap request size and database connections, bound retries with backoff, and return a clear retry signal under overload. Measure admission latency, rejected requests, duplicate receipts, database contention, peak memory and judging backlog during a synchronized submission rehearsal at the intended participant count. Validate restart recovery and zero lost acknowledged submissions before increasing concurrency.

If measurements show the web tier is saturated, add another web process within the Acer’s resource budget. For horizontal scaling across machines, a LAN reverse proxy can distribute requests among trusted Django hosts using the same database, server-side sessions, signing configuration and authoritative time policy. Keep the database on the Acer and restrict its listener to the trusted server network. The Acer remains a single point of failure. If judging is the bottleneck, add a separate isolated judgehost on the reserved wired network instead.

## First prototype and build order

1. **Prove the judge contract.** Use a single problem, three samples, two hidden cases and two test accounts. Verify the selected DOMjudge release can run every applicable case and supply the per-case verdicts and bounded output our adapter needs. Prototype the unscored custom-input path separately. If the available API lacks the needed output, evaluate a small worker-side result collector or an alternative isolated runner before committing to the integration. The custom feedback workflow is a requirement to test, not a verified stock feature.
2. **Finish one contestant journey.** Author and publish that problem locally. Submit a solution that fails one hidden case, save and rerun the case, correct the solution and submit again. Verify the other account cannot fetch the case, and the first contestant earns exactly one solve.
3. **Build the event controls.** Add roster import, contest start/end, jury review, the projector API and manual eligibility decisions. Exercise ties, duplicate requests, late verdicts, rejudging and disconnects.
4. **Rehearse without internet.** Keep the upstream hotspot radio active with mobile data off. Use fresh browsers on both contest bands. Exercise login through standings, restart services with a submission pending, restore a backup, and measure queue times under the expected class load. Use those measurements to set worker concurrency.

The first milestone is complete when an organizer can author a problem, a contestant can debug a failed hidden case and earn a solve, and the projector shows the correct rank with internet access disabled.

## E-Code integration

Open the local portal at http://127.0.0.1:8765/. Students select E-Code student and enter their enrollment and six-digit PIN. Organizers and existing local users select Local account. The organizer navigation includes a searchable roster. Contest standings work offline. Global rankings use the online service and can be filtered by batch.

Run the following from the project folder before the contest while online. The command prompts privately for the deployment's sync secret. Set CODECLASH_SYNC_SECRET in the command environment if using a secret manager.

```bash
cd backend
export LD_LIBRARY_PATH="$PWD/var/maria-runtime/usr/lib/x86_64-linux-gnu"
.venv/bin/python manage.py import_ecode
```

The server calls GET /api/v1/codeclash/roster on ecode-backend.onrender.com and checks the roster count before committing the refresh. It stores enrollment, full name, username and batch locally. PINs are hashed. A refresh deactivates absent E-Code accounts. Conflicting local identities abort the refresh. A student’s five unsuccessful PIN attempts temporarily lock PIN sign-in for five minutes. Verified profile fields are managed at E-Code.

For a finalized contest, validate the outgoing results, then explicitly send them using the same stable external contest ID for that round. Replace LOCAL_ID and EXTERNAL_CONTEST_ID below. Each full solve counts as one point. Historical standings with ambiguous names or unverified identities require organizer reconciliation.

```bash
.venv/bin/python manage.py sync_ecode LOCAL_ID EXTERNAL_CONTEST_ID --check
.venv/bin/python manage.py sync_ecode LOCAL_ID EXTERNAL_CONTEST_ID
```

Result sync sends standings and participant identities. Private source code and PINs stay on the LAN. The read-only global rankings page fetches the published batch list and paginated standings through Django. An external round's raw published standings can also be requested at /api/ecode/leaderboards?contest=EXTERNAL_CONTEST_ID.

</details>
