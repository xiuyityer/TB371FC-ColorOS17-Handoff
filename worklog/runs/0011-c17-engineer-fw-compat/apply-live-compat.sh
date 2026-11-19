#!/system/bin/sh
# Run as root from ADB. Mounts are test-only and disappear on kernel reboot.
set -eu

apply() {
    src=$1
    dest=$2
    original=$3
    expected=$4
    label=$5
    sha256sum "$src" | grep -F "$expected "
    state=$(nsenter -t 1 -m -- sha256sum "$dest")
    case "$state" in
        "$expected "*) return ;;
        "$original "*) ;;
        *) return 1 ;;
    esac
    chown 0:0 "$src"
    chmod 0644 "$src"
    chcon "$label" "$src"
    nsenter -t 1 -m -- mount --bind "$src" "$dest"
    nsenter -t 1 -m -- sha256sum "$dest" | grep -F "$expected "
}

apply /data/local/tmp/c17-wifi-null.pending /apex/com.android.wifi/javalib/service-wifi.jar \
    e89d0c6e143a7da383dcdd604be3976e1d3ae8d28420cfbf710fedfe0e0418c7 \
    0a67dfd88f6e1a2541c824b67ff98aefaeb2d08894b82cdd71c4f96bf789660c u:object_r:system_file:s0
apply /data/local/tmp/c17-qspm-check.pending /system_ext/lib64/libupdateprof.qti.so \
    80b76bd689b8cb10ef430f9de43b837dc1015a1b0ad0396018b604f9d5581c25 \
    b50b14b5d3b742561a7847499df7c75cdbc63b456b45a7f7e907629bd71d0bd9 u:object_r:system_lib_file:s0
setprop ctl.restart zygote
