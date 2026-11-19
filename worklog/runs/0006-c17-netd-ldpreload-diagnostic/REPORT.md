# 0006 C17 netd LD_PRELOAD 诊断（r3）

## 结论

**r3 未修复 netd，C17 仍未完整启动。** 本次取得了两项明确结果：

1. r2 的 BPF 修复继续有效：日志在 `4.405213s` 出现 `NetBpfLoad: success.`，没有回到 `reboot,bpfloader-failed`。
2. `/data/local/tmp/n.so` 的 `LD_PRELOAD` 链路确实生效；最新 tombstone 的崩溃帧和 memory map 都指向该文件，而不是 APEX 内的原库。但 `netd1shot` 仍在 `libnetd_updatable_init.cfi+564` 处 SIGABRT，init 随后执行 `reboot,netd1shot-fail`。

因此，r3 证明了“在 permissive 诊断环境下，可以通过 `/data` 预加载同名库替代 APEX 库”，但**没有证明 25Q2+ 分支补丁已经解决实际内部错误，也没有证明 netd 已越过**。外层 abort PC 与 r2 相同，不能据此武断认定内部失败原因也完全相同。

## 诊断设计与边界

- signed tethering APEX 未修改，AVB/APK 签名未触碰。
- r3 基于已实机验证 BPF 成功的 r2 `system_a`，只修改 inline `netd.rc` 的 2,436 字节原空间，镜像大小不变。
- 在 `netd1shot` 和 `netd` 两个 service 中分别加入：
  `setenv LD_PRELOAD /data/local/tmp/n.so`
- 为保持文件大小不变，只压缩说明性注释；功能性 `persist.vendor.net.doxlat` 触发器保留。
- `libnetd_updatable-r3.so` 仅把文件偏移 `0x62f4` 的 `b.hi 0x6690`（`0x54001ce8`）改成无条件 `b 0x6690`（`0x140000e7`），其余初始化逻辑保留。
- 该方案依赖 `/data/local/tmp/n.so`、`shell_data_file` 标签和 permissive 诊断环境，**不是最终发布修复，也不是 enforcing 方案**。

## 离线验证

- r3 system：954,871,808 字节，SHA-256 `5849cab7d51c99101c5fb0f78a037f1d70b9e0d0b9055f4a9c8272b71dd092fe`。
- r3 netd.rc：SHA-256 `4074b710cfd91f393cc02d1a946e77a2b7781f0b397b869440daaf0486791183`；镜像内回读与 overlay 逐字节一致。
- r3 诊断库：82,760 字节，SHA-256 `d97e4575ecc3c4f06a94e6f7d003729637e021d0dac70dac10524cd68dc88cc3`。
- r3 镜像内 `c17-netbpfload` 回读仍为 r2 `573b70aae730f5b4b4b3216d20fd1c144c208b571f08b161dadb8e1da74f955c`。
- `fsck.erofs` 通过；全量 4,509 inode、3,838 regular files、423 symlinks 的内容、权限、属主和 xattr 回读通过。见 `rom-r3/system_a-readback.json`。
- 可复现构建：`tools/build_netd_diagnostic_r3.py`；反汇编：`evidence/tethering-apex/libnetd_updatable-r3.disasm`。

## 设备写入与 slot

- 写前设备为原版 TWRP、root ADB，recovery 的 `ro.boot.slot_suffix=_b`；C17 写入目标仍明确是 A 槽。
- 写前 A 槽 system 回读为 r2 `a69028ee…dc7f`，防止误覆盖其他版本。
- 仅写 `/dev/block/mapper/system_a`，设备整块回读为 r3 `5849cab7…92fe`。
- 推送诊断库到 `/data/local/tmp/n.so`，属主 root:root、权限 0644，设备回读 SHA-256 与本地一致。
- 未写 super、其他逻辑分区或 recovery；B 槽 C16 内容未改；userdata 未格式化，但本次明确新增了 `/data/local/tmp/n.so`。
- 启动前只清零 `boot_a` 的 80–84 MiB 日志窗口，boot 本体和 KernelSU 未改。
- fastboot 写前显示 `current-slot: b`，执行 `set_active a` 后确认 `current-slot: a`，再 `continue`。因此本次测试的是 A 槽 C17，不是 B 槽 C16。
- 启动监控 240 秒无 Android ADB；随后由用户手动进入原版 TWRP 回读。关机/重启循环不能全部归因于系统自动行为，用户此前说明存在手动按键关机。

## 日志证据

原始窗口：`bootlog-window.bin`，SHA-256 `561de8a41b5b5b93daf66c300f500cff51bd09bdcebf9ec2f3e9a036044e9d`。

- token：`0003-c17-bootlog-20261117-r2`
- CRC32：`127182086`，校验通过。
- `producer_finished=false`：手动进入 TWRP 中断采集进程，不把它当作自然完整结束的日志。
- kmsg：7,750 行、662,647 字节。

关键时间线：

| 时间 | 事件 |
|---|---|
| 4.405213s | `NetBpfLoad: success.` |
| 约 4.406–4.461s | `netd1shot` 启动并很快 SIGABRT |
| 4.462409s | init 收到 `reboot,netd1shot-fail` |
| 4.462885s | init 开始按该原因重启 |

最新证据为 `twrp-readback/_data_tombstones/tombstone_31`（对应 `.pb` 也已保存）：

- `Cmdline: /system/bin/netd oneshot`，pid 1031，signal 6 SIGABRT。
- `#01 pc 0x107ec /data/local/tmp/n.so (libnetd_updatable_init.cfi+564)`。
- BuildID `97ffeaf3cb7c3b1228460563e2887f9b`；4 字节补丁不会改变 BuildID。
- memory map 明确包含 `/data/local/tmp/n.so`，证明不是仍在执行 APEX 原库。

`reboot,/sbin/watchdog` 是 `netd1shot-fail` 之后 watchdogd 请求 reboot 的后续日志，不是新的首因。

## 对补丁的判断与下一步取数

反汇编确认外层包装在 `0x106b8` 调用内部初始化函数 `0x58e8`，随后读取结果对象的错误字段；该字段非零时走 `0x10758`，最终于 `0x107ec` 调用 abort。日志字符串为 `NetdUpdatable` / `libnetd_updatable_init` / `: Failed: `。

r3 只修改 `0x62f4` 的一处版本拒绝分支；当前 tombstone 只证明外层初始化仍返回失败，**没有给出结果对象中的具体内部错误码，不能继续把它简单写成“25Q2+ 拒绝仍在发生”**。

下一轮建议先取准确错误，不要再盲改同一分支：

1. 获取早期 main log 中 `libnetd_updatable_init: Failed: ...` 的完整内容，或在 `0x106bc` 后/ `0x10758` 前增加针对结果对象错误字段的可回读诊断。
2. 结合匹配该 BuildID 的 `NetdUpdatable.cpp` 源码和 `0x58e8` 反汇编定位真正的非零返回路径。
3. 继续保留 r2 BPF 修复；不要因为 netd 失败回退它。
4. 根因明确后再决定系统内置修复；最终必须移除 `/data`/`LD_PRELOAD` 诊断依赖，并单独验证 SELinux enforcing。

## 当前状态

设备停留在用户手动进入的原版 TWRP，root ADB 可用；本次仅回读，未再刷写。A 槽为 C17 r3 + permissive bootlog r2，B 槽保留 C16。`hardware_test_pass=false`，C17 完整启动、netd 修复和 SELinux enforcing 均未完成。
