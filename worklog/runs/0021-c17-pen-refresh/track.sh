#!/system/bin/sh
for n in $(seq 1 125); do
    mode=$(dumpsys display | grep -m 1 'mActiveSfDisplayMode=' | sed 's/.*peakRefreshRate=//;s/,.*//')
    printf '%s hz=%s sel=%s ' "$(cut -d' ' -f1 /proc/uptime)" "$mode" "$(settings get secure oplus_customize_screen_refresh_rate)"
    dumpsys window | grep -m 1 'mCurrentFocus=' | sed 's/^ *//'
    sleep 0.6
done
