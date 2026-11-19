# 0005 C17 netbpfload r2 同大小镜像与实机启动

## 离线候选

- 输入 r1 `system_a`：SHA-256 `decc4b0fbab62d00bb3131f9acfcc48bd127a8cc181b4433492245de8b22e9af`，954,871,808 字节。
- 输出 r2 `system_a`：SHA-256 `a69028ee0f2b0945a8ff4f945109c3e4ef62136616e27aad2b247d35edf8dc7f`，大小完全不变，等于设备 `system_a` extent 的 1,864,984 sectors。
- r1/r2 payload 均为 73,800 字节，只在 `0x68a4` 有 4 字节指令差异。使用现有 LZ4 1.10.0、LZ4HC level 9 重压缩目标主 pcluster；新流为 40,564 字节，与原流长度相同，保留 396 字节前补零。
- 只替换文件偏移 `335,015,936..335,056,896` 的 40,960 字节。inode format 6、NID 11242026、superblock、LP 布局均未改变。
- LZ4 解压—重压缩—再解压往返通过；`fsck.erofs` 返回 0；镜像内目标文件回读 SHA-256 为 `573b70aae730f5b4b4b3216d20fd1c144c208b571f08b161dadb8e1da74f955c`。
- 全量回读通过：4,509 inodes、3,838 regular files、1,511,426,960 file bytes、423 symlinks，权限、属主和 xattr 匹配。见 `rom-r2/system_a.json`、`rom-r2/system_a-readback.json`。
- 追加未压缩数据的旧实验品超区 77,824 字节，已改名保留为 `rom-r2/system_a.append-too-large.img`，从未刷入。

## 设备写入

- 写前设备为原版 TWRP、root ADB、slot `_a`；`/dev/block/mapper/system_a -> /dev/block/dm-0`，1,864,984 sectors。
- 写前设备 system SHA-256 为 r1 `decc4b0f…e9af`。
- 仅推送并写入 `/dev/block/mapper/system_a`；写后整块设备回读 SHA-256 为 `a69028ee0f2b0945a8ff4f945109c3e4ef62136616e27aad2b247d35edf8dc7f`，与本地一致。
- 未写 super、其他逻辑分区、recovery 或 userdata。
- 当前 boot 在去除 80–84 MiB 日志窗口后为 `1bb51df0c5064cf0b08c775b6f9c23a30b74e109a46c603a6a7c291147fc80b1`，与本地 `rom-r1/bootlog-r2-permissive/boot_a.img` 一致。写前设备整 boot 哈希 `62f719…28ec` 的差异是 run 0004 日志，不是另一版内核。
- 启动前只清零该 4 MiB 日志窗口，标准化 boot 哈希再次核对为 `1bb51df0…80b1`。run 0004 原始日志已独立保存。

## 启动结果

- 从 TWRP 重启后连续 40 次、每 5 秒查询，约 200 秒均为 `no-adb`；未出现 `sys.boot_completed=1`。
- 随后 `adb devices -l` 与 `fastboot devices` 都无设备记录，由用户手动进入原版 TWRP 完成回读。

## TWRP 回读后的最终结论（run 0006 前已确认）

- 原始窗口 SHA-256 `9a900801c2b18249ce8ddabeb182a2d5b481a351bf311d31f442a065e3c04a753ef5a3`，token 与 CRC 校验通过；`producer_finished=false`，因为手动进入 TWRP 中断采集。
- **r2 修复实机有效**：日志明确出现 `NetBpfLoad: success.`，`c17_bpfloader` 状态 0 退出，原来的 `reboot,bpfloader-failed` 已消除。
- 新的首个明确自动重启点是 `netd1shot` SIGABRT，init 执行 `reboot,netd1shot-fail`。tombstone 指向 tethering `libnetd_updatable.so` 的 `libnetd_updatable_init.cfi+564`。
- 因此本 run 可以标记为“BPF 修复通过、完整启动未通过”；后续 r3 的 netd 诊断及最终结果见 `runs/0006-c17-netd-ldpreload-diagnostic/REPORT.md`。

`hardware_test_pass=false`；SELinux enforcing 仍是独立未决问题。
