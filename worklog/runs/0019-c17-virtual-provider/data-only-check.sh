#!/system/bin/sh
set -eu
test "$(getprop ro.product.board)" = spinel
sub=$(settings get global multi_sim_data_call)
case "$sub" in ''|*[!0-9]*) exit 2;; esac
if ! ip -o route show table all | grep -q '^default .* dev wlan0 '; then
    echo "No normal Wi-Fi default route before test"
    exit 2
fi
trap 'cmd wifi stop-restricting-auto-join-to-subscription-id' EXIT
cmd wifi start-restricting-auto-join-to-subscription-id "$sub"
for delay in 1 2 3 4 5 6 7 8; do
    sleep 2
    date -Iseconds
    ip -brief addr show | awk '$1 == "wlan0" || $1 ~ /^ovnet/'
    ip -o route show table all | grep -E '^default .* dev (wlan0|ovnet)|^default dev ovnet' || true
    if ! ip -o route show table all | grep -q '^default .* dev wlan0 '; then
        for nic in ovnet0 ovnet1 ovnet2; do
            if ip -o -4 addr show dev "$nic" scope global | grep -q .; then
                ping -I "$nic" -c 2 -W 2 1.1.1.1 || true
                exit
            fi
        done
    fi
done
