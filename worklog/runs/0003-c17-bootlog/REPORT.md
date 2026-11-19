# 0003 C17 KernelSU 早期 kmsg 回读

## 结果

- `rom-r1/bootlog-r1/boot_a.img`，原始候选 SHA-256：`e2c7dfca9d69ba13ab80429e119274690d039508e3de169b45364a4b5ce1ec25`。
- 仅刷写 `boot_a`；未重刷 super，未格式化 data。
- 同一日志程序先在 TWRP `/tmp` 内存文件中自测：token 唯一、CRC 通过、`producer_finished=true`。
- 用户提供的 `twrp_3.7.1.img` 后来写入当时的 B 槽 recovery；随后也为 A 槽写入相同 TWRP，避免返回原厂 Recovery。
- C17 启动后回读 `boot_a` `[80 MiB, 84 MiB)`，日志归属 token `0003-c17-bootlog-20261117-r1`，CRC 通过。
- 原始窗口：`bootlog-window.bin`；解码结果：`bootlog-decoded/`。
- 日志共 3343 行、193946 bytes；EROFS r2、13 个逻辑分区、fstab 和 KernelSU hook 均已执行。
- 最后阶段为约 2.7 秒 SELinux policy load；相比可启动 C16，未出现后续 `enforcing=1`、file contexts 和 `init second stage started`。
- 此状态为 `FAILURE_ATTRIBUTED_KERNELSU_EROFS_PASS_SELINUX_TRANSITION_UNRESOLVED`，不是 boot 成功。

## 关键证据

`bootlog-decoded/manifest.json` 的 `attributed_bootlog` 和 `header_crc_pass` 均为 true。`bootlog-decoded/kmsg.txt` 包含：

- `init: finit_module for '/erofs.ko' succeeded`
- `C17_EROFS_LOAD ... slot a 13/13 mapped`
- `SELinux:  policy capability network_peer_controls=1`

## 下一步

执行单变量 `androidboot.selinux=permissive` 诊断，详见 run 0004。不要将此诊断参数称为最终 SELinux 修复。
