#!/bin/sh
set -eu
cd "$(dirname "$0")"

serial=
state_dir=flash-state
mode=new
check=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --check) check=1 ;;
        --resume) [ "$mode" = new ]; mode=resume ;;
        --restart) [ "$mode" = new ]; mode=restart ;;
        --serial) shift; serial="$1" ;;
        --state-dir) shift; state_dir="$1" ;;
        *) printf '未知参数 / Unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done

if [ "$check" = 0 ]; then
    printf '%s\n' '此操作将清除平板的所有用户数据，包括应用、照片和本地文件。'
    printf '%s' '输入 WIPE 同意并开始刷机，其他输入取消 [默认取消] > '
    if ! IFS= read -r answer || [ "$answer" != WIPE ]; then
        printf '\n%s\n' '已取消，未清除数据或刷入镜像。'
        exit 0
    fi
fi

fail() { printf '%s\n' "$*" >&2; exit 1; }
printf '%s\n' '正在校验镜像和刷写清单…'
shasum -a 256 -c payload.sha256 --status || fail '校验失败，请重新解压刷机包。'
[ "$check" = 0 ] || { printf '%s\n' '离线校验通过。'; exit 0; }

fastboot=./tools/macos/fastboot
devices=$("$fastboot" devices | awk '$2 == "fastboot" {print $1}')
if [ -z "$serial" ]; then
    [ "$(printf '%s\n' "$devices" | awk 'NF{n++} END {print n+0}')" = 1 ] ||
        fail '请连接一台处在 Bootloader Fastboot 的平板，或用 --serial 指定设备。'
    serial="$devices"
fi
case "$serial" in ''|*[!A-Za-z0-9_.-]*) fail '无效的设备序列号。' ;; esac
printf '%s\n' "$devices" | grep -Fxq "$serial" || fail '指定设备不在 Fastboot。'

mkdir -p "$state_dir"
checkpoint="$state_dir/$serial.progress"
log="$state_dir/$serial.log"
fb() {
    printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$log"
    if output=$("$fastboot" -s "$serial" "$@" 2>&1); then
        printf '%s\n' "$output" >>"$log"
        printf '%s\n' "$output"
    else
        printf '%s\n' "$output" >>"$log"
        printf '%s\n' "$output" >&2
        return 1
    fi
}
getvar() {
    output=$(fb getvar "$1") || return
    value=$(printf '%s\n' "$output" | awk -v key="$1:" '$1 == key {print $2}')
    [ -n "$value" ] || fail "设备未返回 $1。"
    printf '%s\n' "$value"
}
[ "$(getvar product)" = spinel ] || fail '仅支持联想 TB371FC（spinel）。'
[ "$(getvar unlocked)" = yes ] || fail '设备的 Bootloader 尚未解锁。'
[ "$(getvar is-userspace)" = no ] || fail '请进入 Bootloader Fastboot。'
for part in super boot_a recovery_a; do
    case "$part" in super) size=12884901888 ;; boot_a) size=100663296 ;; recovery_a) size=104857600 ;; esac
    found=$(getvar "partition-size:$part")
    [ "$((found))" -eq "$size" ] || fail "分区尺寸不匹配：$part"
done
for part in userdata metadata; do
    found=$(getvar "partition-size:$part")
    [ "$((found))" -gt 0 ] || fail "没有预期的数据分区：$part"
done
limit=$(getvar max-download-size)
[ "$((limit))" -ge 100663296 ] || fail 'Fastboot 下载上限低于镜像尺寸。'
case "$(getvar current-slot)" in a|b) ;; *) fail '无法识别当前槽位。' ;; esac

identity=$(shasum -a 256 payload.sha256 | cut -d ' ' -f1)
total=$(wc -l < flash-plan.tsv | tr -d ' ')
next=0
save() { printf '%s %s\n' "$identity" "$1" > "$checkpoint.tmp"; mv -f "$checkpoint.tmp" "$checkpoint"; }
case "$mode" in
    resume)
        [ -f "$checkpoint" ] || fail '没有可续刷的断点。'
        read -r saved next < "$checkpoint"
        [ "$identity" = "$saved" ] || fail '断点属于其他刷机包。'
        case "$next" in ''|*[!0-9]*) fail '无效的断点。' ;; esac
        [ "$next" -le "$total" ] || fail '无效的断点。'
        printf '从已确认的第 %s 步继续。\n' "$next"
        ;;
    restart) save 0 ;;
    *) [ ! -e "$checkpoint" ] || fail '已有刷机记录。使用 --resume 续刷，或 --restart 从头开始。'; save 0 ;;
esac

tab=$(printf '\t')
step=0
while IFS="$tab" read -r action part image; do
    step=$((step + 1))
    [ "$step" -gt "$next" ] || continue
    case "$action:$part" in
        flash:recovery_a|flash:super|flash:boot_a) fb flash "$part" "$image" >/dev/null ;;
        erase:userdata|erase:metadata) fb erase "$part" >/dev/null ;;
        set_active:a) fb set_active a >/dev/null ;;
        *) fail '刷写清单含未知操作。' ;;
    esac
    save "$step"
    if [ "$part" != super ] || [ "$((step % 20))" -eq 0 ]; then
        printf '完成 %s/%s  %s %s\n' "$step" "$total" "$action" "$part"
    fi
done < flash-plan.tsv
[ "$(getvar current-slot)" = a ] || fail 'A 槽切换未确认。'
fb reboot
printf '%s\n' '镜像刷入和用户数据清除已完成，请在平板上完成首次设置。'
