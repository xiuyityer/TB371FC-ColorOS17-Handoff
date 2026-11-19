#!/system/bin/sh
set -eu
umask 077
state=/data/misc/c17-pen-refresh
binary=/system_ext/bin/c17-pen-refresh
config=/my_product/etc/refresh_rate_config.xml

[ "$(getprop ro.product.board)" = spinel ] || exit 0
[ "$(am get-current-user)" = 0 ] || exit 0
[ ! -L "$state" ] || exit 1
mkdir -p "$state"
chmod 0700 "$state"

# Recover a previous interrupted pen vote before selecting the idle rate.
"$binary" --restore "$state" "$state"
[ ! -e "$state/disable" ] || exit 0

# Do not start with a mismatched my_product image or the stock 120 Hz cap.
grep -q '<config defaultMaxRate="144" ipePencilRateId="3" maxrefreshsettings="4"' "$config" || exit 1

native=$(settings get secure oplus_customize_screen_refresh_rate)
peak=$(settings get system peak_refresh_rate)
case "$native:$peak" in
    3:null|3:120|3:120.0|3:120.00001|4:null|4:120|4:120.0|4:120.00001|null:null)
        settings put secure oplus_customize_screen_refresh_rate 4
        settings put system peak_refresh_rate 144.00002
        ;;
esac

if [ -f "$state/bridge.log" ] && [ "$(wc -c < "$state/bridge.log")" -gt 262144 ]; then
    mv -f "$state/bridge.log" "$state/bridge.previous.log"
fi
exec "$binary" --run "$state" "$state" </dev/null >>"$state/bridge.log" 2>&1
