# run 0007 · netd 失败消息采集（2026-11-18）

run 0006 的内核日志表明 logd 已运行，netd1shot 约在 55 ms 后 SIGABRT。已保存的 tombstone 只有 abort 调用栈，已保存的 kmsg 里没有完整的 NetdUpdatable 错误文本。前次 logcat 订阅存在，但其文件没有出现在该次 TWRP 回读中。现在仍需读取内部失败原因。

诊断库 `netd-abort-message.so` 基于原 run 0006 的 r3 库。虚拟地址和文件偏移 `0x10798` 的 AArch64 指令从 `0x52800083` 改为 `0x528000c3`，把错误分支里 LogMessage 的 ERROR (4) 提升为 FATAL (6)。保留既有错误对象的字符串格式化、初始化逻辑和之后的 abort。AOSP libbase 的默认 FATAL 处理会记录 abort message 后终止进程。实际 donor 运行时是否按该路径记录，需通过实机 tombstone 查证。

- 输入 SHA-256 `d97e4575ecc3c4f06a94e6f7d003729637e021d0dac70dac10524cd68dc88cc3`
- 输出 SHA-256 `c0165dad6e99e7d11f26b10429de979223c4618e298e1a85c5dc8d6382afaa20`
- 精确改动见 `patch-disassembly.txt`。BuildID 沿用，归属应同时核对文件哈希和本轮启动时间。
- 参考 [AOSP 日志等级](https://android.googlesource.com/platform/system/libbase/+/refs/heads/main/include/android-base/logging.h) 和 [libbase FATAL 处理](https://android.googlesource.com/platform/system/libbase/+/refs/heads/main/logging.cpp)。

旧 platform-tools 路径已不存在，已从 Google 官方 SDK 下载到 `c17-port/host-tools/platform-tools/`。初次 FASTBOOT 枚举后 USB 断开，随后原版 TWRP 重新上线。

- 原版 TWRP 缩写版本 3.7.1，设备 DEVICE_SERIAL / TB371FC。A 槽 r3 system 整块 SHA-256 与 run 0006 一致，boot 归零日志区后的哈希与原 permissive bootlog r2 一致。
- 已仅替换 `/data/local/tmp/n.so` 并验证设备端 SHA-256、权限及 SELinux 标签。启动前已记录 tombstone 哈希。
- 由 Fastboot 从 B 明确切换到 A。A 槽确认后 `continue` 返回 OKAY。Android ADB 暂未上线。尝试 `reboot recovery` 超时 15 秒，等待原版 TWRP 在线。
- 待办是用 `readback-from-twrp.py` 对照旧 tombstone 哈希采集新增崩溃记录和 boot 日志窗口。尚无新 abort message，无法确认根因。

实机命令及证据见本目录 `stage-console.txt`、`fastboot-console.txt`、`boot-normalized-sha256.txt`、`tombstones-before.sha256` 和 `state.json`。

离线核对 donor tethering APEX 的 libbase.so，BuildID 与 run 0006 tombstone 的映射一致。反汇编证实该库针对等级 6 调用 android_set_abort_message，见 apex-libbase-fatal.txt。

原版 TWRP 已完成回读。tombstone_27 至 tombstone_31 均是相对启动前哈希变化的文件，均明确报告 prog_netd_egress_stats 不存在。bootlog CRC 通过，加载器因 API 3700 不在 [3300, 3600) 跳过两个 4.19 stats 记录，然后仍报告 NetBpfLoad success，netd1shot 随后触发重启。两个程序均存在于 donor-netd.o 的 ELF 中。
