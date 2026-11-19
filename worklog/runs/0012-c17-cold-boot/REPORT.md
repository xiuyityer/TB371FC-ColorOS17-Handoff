# Run 0012 · C17 冷启动

设备 DEVICE_SERIAL，TB371FC/spinel，A 槽。只写入 system_a。原版 TWRP 3.7.1_12-0 和分区全量哈希由 stage-console.txt 记录。镜像大小 954,871,808 字节，写前 SHA-256 为 run 0011 的 `76f665ffbbe2c5126993bbad1887b2532c7064b5de7eb364675de54f11b5308e`，写入并回读 SHA-256 为 `49ea8a803630cfea164bf8e2cb4f4a274663998fc390e45cdfe082bd5fd4f68b`。

`netbpfload.rc` 在 post-fs-data 完成后、zygote-start 之前由 init 绑定两处 run 0011 补丁。文件来自 root 0700 的 `/data/adb/c17-port`，见 data-inputs.txt。Wi-Fi 和 QSPM 原始 APEX 或 system_ext 无改写。这一候选仍有 userdata 文件依赖。保留 run 0011 工程服务修复和 run 0010 的 4.19.325-perf+ 内核。

新 boot ID `REDACTED`，14:37:11 到 14:39:51 PID 2402 未变，`sys.boot_completed=1`、`bootanim=stopped`、`bpf.progs_loaded=1`。两处挂载内容在 system_server 的命名空间中回读匹配。KernelSU 的 shell 提权通过。Wi-Fi 设置开启，完整联网验证未做。启动期间有三次 Oplus `gpuservice` 的 PreCacheService 空指针 SIGSEGV，见 stable-crash.txt，未拖垮 system_server。

VINTF 弹窗仍有。直接调用当前 ROM 的 libvintf 得到第一处失败为 framework matrix 缺少 SELinux policy 30.0，虽已有 30.0.cil 映射。临时绑定补齐该版本后，检查进一步指出 framework manifest 缺 VNDK 30 声明。实际 `com.android.vndk.v30` APEX 已挂载，vendor namespace 的 linkerconfig 搜索路径已指向它。临时绑定补齐两处后完整检查和仅 manifest 检查都返回 0。两 XML 作为 run 0013 的输入。
