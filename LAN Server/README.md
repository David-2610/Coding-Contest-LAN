# CodeClash LAN deployment

Use the [CodeClash 1.0 operating guide](../Coding%20Contest%20Server/OPERATIONS.md) for the current install, DNS name and client acceptance procedure.

<details><summary>Earlier network milestone and recovery notes</summary>

# Coding Contest LAN

This project lets participants open the same offline test page on either of two Wi-Fi networks hosted by the Acer Nitro ANV15-51. The Acer stays connected to the organizer’s 5 GHz phone hotspot. Participants join **Coding LAN 5 GHz** or **Coding LAN 2.4 GHz** and open [the contest page](http://contest.test/). Both networks use the same fixed contest password.

## Run a session

**If the LAN is already confirmed**, use `sudo contest-lan status`. Three active service units and an inactive rollback timer are expected. You can close the terminal.

**To start a new session**, connect the built-in Wi-Fi to the 5 GHz phone hotspot and plug in the ProDot. Leave the ProDot disconnected from other Wi-Fi networks. On the Acer, run:

```bash
sudo contest-lan preflight && sudo contest-lan start
```

1. On a second phone, join **Coding LAN 2.4 GHz**. Choose to stay on the network if the phone reports no internet.
2. Open [the page by IP](http://10.50.0.1/) and [by hostname](http://contest.test/). Both should show **Contest LAN is online**. Repeat on **Coding LAN 5 GHz**.
3. Check that the Acer still shows its mobile hotspot connection. Within **five minutes of startup**, run:

```bash
sudo contest-lan confirm
```

The CLI prints `Confirmed` and cancels the rollback timer. To finish the session, run `sudo contest-lan stop`.

**After a reboot**, startup is manual. Reconnect the Acer to the 5 GHz hotspot and plug in the ProDot. Run `sudo contest-lan recover` to clear any previous run state, then follow the start, test and confirm steps above. During a live session, `recover` takes the contest networks down.

## Install or update

The daily commands above use the installed copy. To install from this project on the configured Acer:

```bash
cd "$HOME/Launchpad/Coding Contest LAN/LAN Server"
sudo ./service/install.sh
```

For an update, finish the current session with `sudo contest-lan stop` first. The installer refuses an update while a run record exists. It copies the controller, page and configuration to `/opt/contest-lan` and links the command at `/usr/local/sbin/contest-lan`. Editing this project takes effect after reinstalling and starting a new session.

The Ubuntu host uses systemd, NetworkManager, Python 3, hostapd, dnsmasq, nftables, iw and iproute2. The controller checks its required executables at preflight. Use a local terminal with sudo for radio and firewall operations.

## Architecture

```text
Organizer's phone hotspot (5 GHz)
   └── Acer built-in radio, wlp63s0, connected as a station
        └── same radio and channel, separate AP interface contestap0
             └── Coding LAN 5 GHz participants        ─┐
                                                      ├── contestbr0 · 10.50.0.1/24
ProDot USB radio, channel 6                           │      ├── dnsmasq · DHCP and DNS
   └── Coding LAN 2.4 GHz participants               ─┘      └── Python · HTTP test page
```

The built-in radio supports a station and an access point on the same channel. Startup reads the mobile hotspot channel and uses it for the 5 GHz contest AP. The ProDot W30N uses a separate Realtek RTL8192EU radio, identified by USB ID `0bda:818b`. The controller locates its current interface name and explicitly releases that adapter from NetworkManager for the session. The wired interface `enp64s0` is reserved for future judges.

When a participant joins, **hostapd** authenticates the device. **dnsmasq** leases an address and supplies the Acer as the local DNS server. A lookup for `contest.test` returns the bridge address. The browser then requests the page from the Python HTTP service. The upstream phone keeps its own routing and DNS configuration. Test participant access from a device joined to one of the contest SSIDs.

## Configuration and files

| Setting | Value or source |
|---|---|
| Wireless security | WPA2-PSK with AES-CCMP on both bands. Each SSID has its own derived key for the shared passphrase. |
| 5 GHz AP | Built-in radio, virtual interface `contestap0`, current permitted non-radar 5 GHz hotspot channel |
| 2.4 GHz AP | ProDot USB radio, channel 6 at 2437 MHz |
| Addressing | `10.50.0.0/24`, bridge and advertised gateway `10.50.0.1` |
| DHCP | `10.50.0.50` through `10.50.0.249`, four-hour leases, lease file `/run/contest-lan.leases` |
| DNS | `contest.test` resolves to `10.50.0.1`. dnsmasq binds to the contest bridge and uses local records. |
| HTTP | `10.50.0.1:80/`, served by a transient systemd service with a dynamic user |
| Participant access | DHCP, local DNS over TCP/UDP, and local HTTP. Other participant-to-host traffic, including IPv6, drops. IP forwarding involving the contest bridge drops in both directions. |
| Client isolation | hostapd requests same-AP station isolation. The bridge firewall blocks frames forwarded between contest ports. |
| Upstream reachability | The participant filter applies to the contest bridge. An upstream device with an explicit route is a separate case. |

| Project file | What it controls |
|---|---|
| [service/contest-lan](service/contest-lan) | CLI, hardware detection, radio names and keys, generated hostapd configs, health checks, rollback |
| [service/host installer](service/install.sh) | Installed file locations and permissions |
| [service/dnsmasq.conf](service/dnsmasq.conf) | DHCP pool, lease time, DNS record, gateway and DNS options |
| [service/firewall.nft](service/firewall.nft) | IPv4/IPv6 input and forwarding rules, plus bridge filtering |
| [service/page.py](service/page.py) | Local HTTP server and landing-page text |
| [tests](tests/) | Recovery simulation and isolated network tests |
| [releases](releases/) | Portable installation archive for the current working build |

For a page change, edit `service/page.py`. For an address or hostname change, update the controller health checks, DHCP/DNS settings, firewall, tests and guide together. A Wi-Fi name or password change requires recomputing each SSID’s WPA2 key from the passphrase and exact SSID (PBKDF2-HMAC-SHA1, 4096 iterations, 32 bytes). Treat the controller and release archive as credentials because they contain usable derived keys.

## Startup and recovery

1. Preflight checks radio capabilities, hotspot state and channel, USB availability, subnet overlap, existing resource names and configuration syntax.
2. Startup saves the previous state, arms a five-minute systemd rollback timer and installs the contest filters. It reserves the virtual devices with a runtime NetworkManager rule, releases the ProDot, creates the bridge and adds the 5 GHz AP interface.
3. Three transient services run the page, dnsmasq and hostapd. The controller checks both radio frequencies, bridge membership, the uplink profile, both firewall tables, the local DNS answer and the HTTP response.
4. A startup failure or an unconfirmed timeout invokes recovery. Stop and recover use the run record to remove the contest resources and return the ProDot to NetworkManager. Confirmation keeps the services running for the current boot.

| Location on the Acer | Contents |
|---|---|
| `/var/lib/contest-lan/active.json` | Current run and recovery progress |
| `/var/lib/contest-lan/run-*/` | Root-only snapshots, pre-start firewall rules and generated per-radio hostapd configs |
| `/run/NetworkManager/conf.d/91-contest-lan.conf` | Temporary ownership rules for the virtual AP and bridge |
| `/run/contest-lan-ap/` | hostapd control sockets for the active radios |
| systemd journal | Service events from `contest-lan-ap`, `contest-lan-dns`, `contest-lan-page`, and rollback |

Use `sudo contest-lan recover` after an interrupted stop or startup. If it reports a failure, correct the reported condition and retry. Keep the run record available until recovery finishes. The firewall snapshot is for inspection. Replacing the entire host ruleset would affect unrelated networking.

## Diagnose a problem

| Symptom | First check |
|---|---|
| No contest networks or SSIDs disappeared | Run `sudo contest-lan status` and `sudo contest-lan diagnostics`. An unconfirmed startup expires after five minutes. |
| Preflight rejects the hotspot or channel | Use `iw dev wlp63s0 info` to check the active 5 GHz channel. Connect to an AP-permitted non-radar channel. |
| ProDot unavailable | Check `lsusb` and `nmcli device status`. Before startup the USB adapter should be plugged in, disconnected and managed by NetworkManager. |
| Phone joins but neither URL opens | Verify the phone has a contest-pool address, DNS and gateway. Choose to stay on the offline Wi-Fi and use the explicit HTTP address. |
| IP works but hostname fails | Check DNS is `10.50.0.1`. Temporarily pause any forced private DNS, browser secure DNS, VPN or mobile-data fallback and retry. Restore the settings after testing. |
| One band fails | Run `iw dev` and `bridge link show master contestbr0`. Check the AP journal for association and the DHCP journal for a lease on the affected device. |

```bash
sudo contest-lan status
sudo contest-lan diagnostics
sudo journalctl -b -u contest-lan-ap -u contest-lan-dns -u contest-lan-page --no-pager -n 80
```

## Verification and scope

The operator reported reaching the contest server over both physical bands and receiving the CLI’s confirmation. The test page verifies connectivity. The current implementation serves that page only. Contest judging and the operator dashboard are future work.

From the project root, run these local checks as your usual user:

```bash
cd "$HOME/Launchpad/Coding Contest LAN/LAN Server"
python3 tests/recovery.py
bash tests/network.sh
```

The recovery simulation injects startup failures and checks repeatable cleanup. The network test creates disposable network namespaces, a bridge and two virtual clients. It checks DHCP, local DNS and HTTP, cross-port isolation, host port filtering and forwarding drops. It requires user/network namespace support, busybox udhcpc, dig, ping and the host networking tools. Physical association and same-radio isolation are separate device tests.

For a future incident dashboard, capture hostapd association events with run and boot IDs, UTC time, monotonic time and observer health. Compute observed durations only within continuous coverage. Record suspend, restarts and missing events as unknown intervals. Keep operator decisions and reasons separate from radio observations.

</details>
