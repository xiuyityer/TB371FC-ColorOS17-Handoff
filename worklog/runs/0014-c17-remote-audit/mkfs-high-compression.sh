#!/bin/bash
set -eu
workspace=$(cd -- "$(dirname -- "$0")/../../.." && pwd)
args=()
for arg in "$@"; do
    if [[ $arg == -zlz4hc,9 ]]; then
        arg=-zlz4hc,12
    fi
    args+=("$arg")
done
exec "$workspace/tool-src/erofs-utils-1.8.10/mkfs/mkfs.erofs" "${args[@]}"
