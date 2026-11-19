#!/system/bin/sh
set -eu
umask 077
[ "$(getprop ro.boot.slot_suffix)" = _a ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(getprop init.svc.c17_pen_refresh)" = running ]
modules=/data/adb/modules
retired=/data/adb/c17-retired-modules/run0017
state=/data/misc/c17-ai-controls
mkdir -p "$retired" "$state"
chmod 0700 "$retired" "$state"
pen_old=/data/adb/r94_pen_refresh_bridge/checkpoint
[ ! -e "$pen_old" ]
if grep -q /data/adb/modules /proc/1/mountinfo; then
    echo "module mount detected, stopping" >&2
    exit 1
fi
old="$modules/r94_ai_transaction_candidate/state.txt"
if [ -f "$old" ] && [ ! -e "$state/state.txt" ]; then
    awk '
        NR==FNR {allowed[$1]=1; next}
        NF!=2 || !($1 in allowed) || seen[$1]++ || ($2!=0 && $2!=1) {exit 1}
    ' /system_ext/etc/c17-port/ai-packages.txt "$old"
    cp "$old" "$state/state.legacy"
    chmod 0600 "$state/state.legacy"
    mv "$state/state.legacy" "$state/state.txt"
    echo AI_RESTORE_STATE_MIGRATED
fi
for id in r94_ai_transaction_candidate r94_bili_native_rules r94_foreground_schedtune r94_pen_refresh_bridge r94_privacy_password_test r94_speaker_direction; do
    if [ -d "$modules/$id" ]; then
        [ ! -e "$retired/$id" ]
        grep -Fx "id=$id" "$modules/$id/module.prop" >/dev/null
        mv "$modules/$id" "$retired/$id"
        echo "RETIRED $id"
    fi
done
find "$modules" -mindepth 2 -maxdepth 2 -name module.prop -print
