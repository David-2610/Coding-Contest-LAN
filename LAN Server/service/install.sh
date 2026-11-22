#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -e /var/lib/contest-lan/active.json ]; then
    echo 'First run sudo contest-lan stop using the currently installed version.' >&2
    exit 1
fi
install -d -m 755 /opt/contest-lan /usr/local/sbin
install -m 644 page.py dnsmasq.conf firewall.nft /opt/contest-lan/
install -m 700 contest-lan /opt/contest-lan/
ln -sfn /opt/contest-lan/contest-lan /usr/local/sbin/contest-lan
