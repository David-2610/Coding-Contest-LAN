# CodeClash 1.0 on the Acer

## Before the round

Use the Acer terminal. The Django application serves the bundled React UI. Two loopback web workers use the local MariaDB socket. A separate single-slot worker executes submissions and a presence observer checks for missed heartbeats.

```bash
cd "$HOME/Launchpad/Coding Contest LAN/Coding Contest Server/backend"
scripts/server start
export LD_LIBRARY_PATH="$PWD/var/maria-runtime/usr/lib/x86_64-linux-gnu"
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py import_ecode
```

Import prompts for the deployment sync secret. The authenticated HTTPS roster supplies enrollment, username, full name, batch and a six-digit PIN. Enrollment is the unique upstream key in the supplied contract. It contains no separate Firebase UID. Refresh while online before each event. The imported PIN verifier works during an internet outage. Withdrawn students lose access on refresh. A failed refresh rolls back. Avoid running with a stale roster following an upstream revocation. Local participant signup and profile editing are disabled. Independent pilot accounts cannot sign in.

Use the same sign-in form on the Acer at http://127.0.0.1:8765/ with username organizer. To rotate the organizer credential, run the following from backend with the library path set as above. On a fresh database first use manage.py createsuperuser --username organizer. The former pilot installer may have left an old password in backend/var/pilot-logins. Rotation invalidates that password.

```bash
.venv/bin/python manage.py changepassword organizer
```

## Authoring and running a contest

Create the draft, select Problems, then Add problem. Download the JSON example and schema. One file contains one complete stdin/stdout question. Each case has a unique ID, input string, expected output string, visibility and weight. The all-or-nothing scoring method awards maxScore once for the first full solve. Per-case weights do not yield partial credit. Configure case limits in milliseconds and MiB. The preview shows examples and case counts. Confirm the import, or explicitly select replacement before starting the round. Existing function-based questions retain their original drivers.

Schedule the round, open the waiting room, then start it. The original scheduled duration is measured from the actual start. Students acknowledge instructions before admission. End the round explicitly or let the deadline pass. Pending official submissions finish before the standings are frozen. Final editor drafts enter the archive queue. Use the organizer standings tab to download the final JSON.

## Bring up both Wi-Fi bands

Connect the Acer internal Wi-Fi to the 5 GHz upstream hotspot and attach the 2.4 GHz USB adapter. Start the database and contest services first. If an older contest AP is active, stop it at a planned interruption using sudo contest-lan stop. Install from the updated service directory on this Acer.

```bash
cd "$HOME/Launchpad/Coding Contest LAN/LAN Server/service"
sudo ./install.sh
sudo contest-lan preflight
sudo contest-lan start
```

Both SSIDs join contestbr0. dnsmasq assigns addresses and advertises 10.50.0.1 as DNS on both. The bridge-scoped DNS record resolves codeclash.test to the Acer. Gunicorn binds directly to 10.50.0.1:80 as the desktop user with the port-binding capability. The firewall admits DHCP, DNS and HTTP on the contest bridge. Client-to-client forwarding is blocked. The installation uses the current Launchpad path and intercom account. On another machine update these values first.

On a separate device join each SSID in turn. Stay connected if the OS warns that the network has no internet. Visit http://codeclash.test/ and verify the login screen. Refresh /login/ and open /api/session. Where available, run nslookup codeclash.test and check both the DNS server and returned address are 10.50.0.1. Check the lease is in the .50–.249 range. Strict Private DNS, VPNs and browser DNS-over-HTTPS can bypass DHCP DNS. Use the contest network’s resolver for this test. The .test suffix avoids conflicting with a publicly registered .com. HTTP on the isolated WPA2 network has no browser-level encryption. For TLS on unmanaged devices use an owned domain with an advance-issued trusted certificate and local DNS pointing to the Acer.

After both bands pass and the upstream link still works, run sudo contest-lan confirm on the Acer within the startup window. Use sudo contest-lan status or sudo contest-lan diagnostics to inspect failures. Use sudo contest-lan stop to end the LAN.

## Monitoring and capacity

An authenticated open workspace sends a heartbeat after a random initial delay and then every 9–11 seconds. Tabs update the same participant entry. Server receipt time drives status. The default unstable threshold is 20 seconds and disconnection threshold is 40 seconds, with observer checks about every four seconds. Set CONTEST_UNSTABLE_SECONDS and CONTEST_DISCONNECT_SECONDS consistently for web and presence services to override them. Observer gaps are recorded separately. Reconnection is logged. A sleeping browser can miss heartbeats while Wi-Fi is still associated. A human organizer reviews the activity and records a reason for disqualification or reversal. New submissions are blocked server-side immediately. An open workspace displays the decision on its next successful heartbeat.

The DHCP range supplies 200 leases across both radios. The Acer reports 16 logical processors and about 14 GiB RAM. One radio advertises 127 associated stations and the other provides no observed numerical limit. MariaDB allows 24 connections and the system runs one judge job at a time. These figures cannot establish a tested simultaneous participant maximum.

| Participants | Mean workspace heartbeats/s | Capacity check |
| --- | ---: | --- |
| 20 | 2 | Rehearse a synchronized submission round and measure the last verdict. |
| 50 | 5 | Check airtime, retries and median and worst queue delay on both radios. |
| 100 | 10 | Divide devices across bands and measure both Wi-Fi loss and judge backlog. |
| 200 | 20 | All DHCP leases would be occupied. Reserve address headroom and benchmark additional APs and judge capacity before scheduling. |

For N simultaneous submissions with average service time T, one judge needs approximately N × T to drain the batch. Rehearse on real devices, recording the first and last receipt and verdict times, CPU, memory, AP associations and missed heartbeats. Add workers only with coordinated job claiming and isolated execution slots.

## Single launcher and organizer transfers

Open **Start CodeClash** on the Acer desktop, or run the executable of the same name in the Coding Contest LAN folder as your normal desktop user. Leave both Wi-Fi adapters available and the internal adapter on the 5 GHz hotspot. Supply the Ubuntu administrator password when prompted. The launcher starts the local services, applies migrations, collects frontend assets, installs and starts the contest AP and DNS, confirms the rollout after the controller’s local health checks, and opens http://codeclash.test/login/ in the default browser. Organizer access on the Acer remains available at http://127.0.0.1:8765/organizer/. The launcher performs confirmation automatically. Physical client checks remain an organizer rehearsal step.

In **Roster**, select **Refresh roster from E-Code** while the Acer is online. A background transfer reconciles enrollment numbers and retains existing account IDs. The deployment credential is stored privately under backend/var. Both web and terminal transfers use it.

Once a contest has frozen standings, select **Organizer → Standings → Send final leaderboard to E-Code** and confirm. The transfer reports the outcome and disables repeat publishing after confirmed success. If a network failure leaves delivery uncertain, check the remote contest record before retrying. New rounds keep a private entry-ID mapping so students sharing a name can be distinguished when publishing.
