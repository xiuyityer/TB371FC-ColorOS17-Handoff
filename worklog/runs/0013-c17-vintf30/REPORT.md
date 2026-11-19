# Run 0013 · C17 VINTF 30 冷启动验证

DEVICE_SERIAL，TB371FC/spinel，A 槽。原版 TWRP 3.7.1_12-0 写入 system_a 后全量读回。写前 SHA-256 `49ea8a803630cfea164bf8e2cb4f4a274663998fc390e45cdfe082bd5fd4f68b`，最终 SHA-256 `97afde2cc1c6c46755dddab55294d63e3a14b848a4787f39dd1306fbd77f3b54`，954,871,808 字节。fastboot 确认 product spinel、current-slot a，continue OKAY。未格式化 userdata。

本次只改两个 framework VINTF XML。framework matrix 新增 SELinux policy 30.0，对应系统现有的 30.0.cil 映射。framework manifest 新增 VNDK 30，对应实机已挂载且 linkerconfig 已引用的 com.android.vndk.v30。保留其他声明。两个补丁文件均位于 system_a 的持久 EROFS 中。build-system.py、candidate.json 和 stage-console.txt 记录构建及设备读回。没有改变兼容性检查逻辑。

14:42:08 至 14:42:56 实机 boot ID `REDACTED`，system_server PID 1857。采集时内核运行 111 秒，`sys.boot_completed=1`、`bootanim=stopped`，窗口的 focused app 为系统桌面。内核 4.19.325-perf+，KernelSU root 通过，`bpf.progs_loaded=1`。完整 VINTF 检查与仅 manifest 检查都返回 0，两个 XML 无临时挂载且回读哈希与候选一致。启动和稳定后日志没有此前两条弹窗告警。

## 剩余事项

- Wi-Fi 和 QSPM 自动加载仍依赖 `/data/adb/c17-port`。netd 另依赖 `/data/local/tmp/c17-bpf/netd.o` 与 `/data/local/tmp/n.so`。下一轮镜像集成需保留签名 APEX，并将依赖移出 userdata。当前仍为 SELinux Permissive。
- Wi-Fi 开启，采集时未连接。后续需单独验证连网。
- 有三次 Oplus gpuservice 的 PreCacheService 空对象崩溃，日志命中 getAppInfo 和 writeAllRePathInfos。settled 时 gpuservice 后续实例 PID 4697 仍运行，system_server 无重启。已保存匹配 BuildID 的 onTransact 反汇编。它从 this+0x68 取 PreCacheService 指针后直接调用，这两条路径没有空指针检查。修复需确认对象初始化分支和各 Binder 事务的不可用返回值，保留正常功能路径。
- 当前设备保持 run 0013 C17 桌面，原版 TWRP 可用。
