#!/bin/bash
# Always run the network fixture in a fresh namespace.
set -euo pipefail
if [[ ${1:-} != --inside-fixture ]]; then
    exec unshare --user --map-root-user --net bash "$0" --inside-fixture
fi
if [[ /proc/self/ns/net -ef /proc/1/ns/net ]]; then
    echo "A private network namespace is required." >&2
    exit 1
fi
base=$(cd "$(dirname "$0")/../service" && pwd)
tmp=$(mktemp -d)
unshare -n sleep 90 &
client=$!
trap 'kill "$client" ${dns:-} ${web:-} ${admin:-} 2>/dev/null || true' EXIT
for x in {1..50}; do [[ $(readlink /proc/self/ns/net) != "$(readlink /proc/$client/ns/net)" ]] && break; sleep .05; done
in_client() { nsenter -t "$client" -n "$@"; }
ip link add contestap0 type veth peer name client0
ip link set client0 netns "$client"
ip link set lo up
ip link add contestbr0 type bridge
ip link set contestap0 master contestbr0
ip link set contestbr0 up
ip addr add 10.50.0.1/24 dev contestbr0
ip -6 addr add fd50::1/64 dev contestbr0 nodad
ip link set contestap0 up
in_client ip link set lo up
in_client ip link set client0 up
nft -c -f "$base/firewall.nft"
nft -f "$base/firewall.nft"
sed "s|/run/contest-lan.leases|$tmp/leases|" "$base/dnsmasq.conf" > "$tmp/dnsmasq.conf"
dnsmasq --no-daemon --conf-file="$tmp/dnsmasq.conf" >"$tmp/dns.log" 2>&1 &
dns=$!
python3 "$base/page.py" 10.50.0.1 80 >"$tmp/web.log" 2>&1 &
web=$!
python3 -m http.server 2222 --bind :: >"$tmp/admin.log" 2>&1 &
admin=$!
sleep .4
cat > "$tmp/lease" <<'SCRIPT'
#!/bin/sh
if [ "$1" = bound ]; then echo "$ip $dns $router" > "$RESULT"; fi
SCRIPT
chmod +x "$tmp/lease"
export RESULT=$tmp/result
if ! in_client busybox udhcpc -i client0 -s "$tmp/lease" -n -q -t 3 -T 3; then cat "$tmp/dns.log"; exit 1; fi
read -r lease resolver gateway < "$RESULT"
[[ $lease == 10.50.0.* && ${lease##*.} -ge 50 && ${lease##*.} -le 249 && $resolver == 10.50.0.1 && $gateway == 10.50.0.1 ]]
in_client ip addr add "$lease/24" dev client0
in_client ip -6 addr add fd50::2/64 dev client0 nodad
[[ $(in_client dig +short @10.50.0.1 contest.test) == 10.50.0.1 ]]
[[ $(in_client dig +tcp +short @10.50.0.1 contest.test) == 10.50.0.1 ]]
in_client python3 -c 'import urllib.request; assert b"Contest LAN is online" in urllib.request.urlopen("http://10.50.0.1/", timeout=3).read()'
# Model the second band with an independent station namespace.
unshare -n sleep 60 &
second=$!
sleep .2
second_client() { nsenter -t "$second" -n "$@"; }
ip link add usbport type veth peer name client2
ip link set client2 netns "$second"
ip link set usbport master contestbr0
ip link set usbport up
second_client ip link set client2 up
second_client busybox udhcpc -i client2 -s "$tmp/lease" -n -q -t 3 -T 3
read -r lease2 resolver gateway < "$RESULT"
[[ "$lease2" != "$lease" && $resolver == 10.50.0.1 && $gateway == 10.50.0.1 ]]
second_client ip addr add "$lease2/24" dev client2
[[ $(second_client dig +short @10.50.0.1 contest.test) == 10.50.0.1 ]]
second_client python3 -c 'import urllib.request; assert b"Contest LAN is online" in urllib.request.urlopen("http://10.50.0.1/",timeout=2).read()'
if second_client ping -I client2 -c 1 -W 1 "$lease"; then exit 1; fi
nft list chain bridge contest_lan forward | grep -E 'counter packets [1-9][0-9]* bytes'
kill "$second"
# Known listeners verify the probes exercise actual services.
python3 -c 'import socket; socket.create_connection(("10.50.0.1",2222),1).close(); socket.create_connection(("fd50::1",2222),1).close()'
in_client python3 - <<'PY'
import socket
for addr in ("10.50.0.1","fd50::1"):
    try: socket.create_connection((addr,2222),1)
    except TimeoutError: pass
    else: raise AssertionError(addr)
PY
# The second veth pair represents a separate network in the test only.
ip link add other0 type veth peer name otherpeer
ip link set otherpeer netns "$client"
ip addr add 192.0.2.1/24 dev other0
ip link set other0 up
in_client ip addr add 192.0.2.2/24 dev otherpeer
in_client ip link set otherpeer up
sysctl -qw net.ipv4.ip_forward=1
in_client ip route add 192.0.2.55/32 via 10.50.0.1 dev client0
in_client ip route add 10.50.0.210/32 via 192.0.2.1 dev otherpeer
# Bind source addresses to satisfy reverse path checks on both ingress links.
in_client ping -I "$lease" -c 1 -W 1 192.0.2.55 >/dev/null || true
in_client ping -I 192.0.2.2 -c 1 -W 1 10.50.0.210 >/dev/null || true
rules=$(nft list chain inet contest_lan forward)
echo "$rules"
[[ $(echo "$rules" | grep -Ec 'counter packets [1-9][0-9]* bytes [0-9]+ drop') == 2 ]]
nft list table inet contest_lan
echo "Virtual client passed DHCP ($lease), DNS UDP/TCP, HTTP and admin-port isolation."
