# 0004 C17 permissive 单变量诊断与 bpfloader 定位

## 候选与设备写入

- boot：`rom-r1/bootlog-r2-permissive/boot_a.img`
- SHA-256：`5b2d4179b95ad3dc023c9c1fe4e7026311a674a3dbbd29f850c8a9cc10d193d7`
- 相对 run 0003，仅追加 `androidboot.selinux=permissive`，日志 token 改为 `0003-c17-bootlog-20261117-r2`。
- KernelSU、#789 内核、DTB、EROFS r2、fstab 和 super 均未改变。
- 同一 TWRP 写入 `recovery_a`，然后刷 `boot_a`、切 A 槽并重启；未刷 super、未清 data。
- 设备随后自动进入 TWRP；用户说明最后关机还包含手动按键，因此 shutdown 尾部不能单独当作自动故障根因。

## 日志结论

原始窗口：`bootlog-window.bin`；解码：`bootlog-decoded/`。

- token 唯一、CRC 通过、`producer_finished=true`。
- 共 7080 行、632528 bytes。
- 已出现 `Loaded file context`、`init second stage started!`、APEX、vold、servicemanager、hwservicemanager，说明 permissive 越过了 run 0003 的 SELinux 阶段。
- 首个明确的自动 reboot 触发点是 `c17-netbpfload` SIGABRT，随后 init 执行服务的 `reboot_on_failure reboot,bpfloader-failed`。

关键日志：

```text
NetBpfLoad: file /apex/com.android.tethering/etc/bpf/mainline/offload.o is on device 1960, while we are on device 64512
init: Service 'c17_bpfloader' (pid 1025) received SIGABRT
init: Service c17_bpfloader has 'reboot_on_failure' option and failed, shutting down system.
init: init reboot in response to powerctl: reboot,bpfloader-failed
```

## 二进制根因与离线补丁

C17 netbpfload 新增检查：BPF 对象的 `st_dev` 必须等于 `/proc/self/exe` 的 `st_dev`。此前为修补最低内核版本，把程序复制到 `/system/bin/c17-netbpfload`（dm 设备 64512），而对象仍在 loop 挂载的 tethering APEX（1960），所以检查必然失败。

原指令位于文件偏移 `0x68a4`：`b.ne 0x6ccc`（`0x54002141`）。r2 仅改为 NOP（`0xd503201f`），保留 ELF、实际 BPF 加载、per-map/program feature gate 和其他失败处理。

- 新文件：`overlays/c17-netbpfload-r2`
- SHA-256：`573b70aae730f5b4b4b3216d20fd1c144c208b571f08b161dadb8e1da74f955c`
- 补丁记录：`evidence/netbpfload-patch-r2.json`
- 反汇编：`evidence/tethering-apex/c17-netbpfload-r2.disasm`
- 新 system overlay 计划：`rom-r2/plans/system.json`

## 当前限制（后续由 run 0005 更新）

本报告末尾此前记录的“`rom-r2/system_a.img` 不存在、r2 尚未进入设备”已被 run 0005 超越：同大小 r2 镜像已通过原物理簇内 LZ4HC 重压缩生成，仅写入 `system_a` 并回读一致。run 0005 启动后约 200 秒无 ADB，正在等待 TWRP 回读，详见 `../0005-c17-netbpfload-r2/REPORT.md`。

另经 run 0005 实时核对，本地当前 permissive boot 及其 manifest 的 SHA-256 为 `1bb51df0c5064cf0b08c775b6f9c23a30b74e109a46c603a6a7c291147fc80b1`；设备整 boot 哈希会因本报告的日志窗口写入而改变，标准化日志窗口后与本地一致。SELinux enforcing 的最终修复仍未完成，permissive 仅用于诊断。
