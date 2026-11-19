#!/system/bin/sh
date -Iseconds
cat /proc/sys/kernel/random/boot_id /proc/uptime
for key in sys.boot_completed init.svc.bootanim ro.boot.slot_suffix init.svc.r94-commcenterd init.svc.c17-virtual-ril-0 init.svc.c17-virtual-ril-1; do
    printf '%s=%s\n' "$key" "$(getprop "$key")"
done
printf 'system_server=%s\nphone=%s\n' "$(pidof system_server)" "$(pidof com.android.phone)"
cmd activity get-started-user-state 0
printf '\nVirtual radio services\n'
service list | grep -E 'vircomm[12]|IDmtpService/default|ISubsysRadio'
printf '\nVirtual network\n'
for nic in ovnet0 ovnet1 ovnet2; do
    dir="/sys/class/net/$nic"
    if [ -d "$dir" ]; then
        printf '%s state=%s tx=%s rx=%s\n' "$nic" "$(cat "$dir/operstate")" "$(cat "$dir/statistics/tx_packets")" "$(cat "$dir/statistics/rx_packets")"
        ip -o addr show dev "$nic" scope global | awk '{print $2, $3, $4}'
    else
        printf '%s missing\n' "$nic"
    fi
done
ip route show table all | grep -E 'ovnet|^default '
