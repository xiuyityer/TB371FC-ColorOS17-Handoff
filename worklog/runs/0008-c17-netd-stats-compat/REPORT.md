# run 0008 · 适配 4.19 流量统计程序（2026-11-18）

run 0007 的五份新 tombstone 明确显示 netd1shot 缺少 prog_netd_egress_stats。bootlog 同时报告 legacy ingress/egress 因 API 3700 超出 [3300,3600) 而跳过。

从 donor tethering APEX 提取原 netd.o（SHA-256 edb24768ebbabe7b923de3770b6034de3657b4c55f80cb8350997c22c663e62e）。通过 ELF .symtab 定位 .android_progs 中两个 stats_4_19_t_def。在 0x2aa9c、0x2b0f0 将 little-endian u32 3600 改为 3701，保留内核范围 [4.19,5.4) 和程序指令。改后 SHA-256 cd5f380b8292a4dfd1b237d976902e02ace4efff068a1f6d61c05d06b185c3e6。

临时加载器以 r2 payload 为输入，仅将单处 NUL 结尾的 /apex/com.android.tethering/etc/bpf/mainline/netd.o 字符串换成 /data/local/tmp/c17-bpf/netd.o，并补零保持尺寸；其余对象、函数、失败处理沿用。保留 signed APEX 文件。诊断对象存放在 root 专用目录。这是实机验证用路径，发布版本需要不依赖 /data 的可复现集成。

在 run 0006 r3 system 原位置替换 40,960 字节 EROFS 主 pcluster。LZ4 回读一致，fsck.erofs 通过，从目标路径读出的加载器全文件与候选相同。镜像 954,871,808 字节，SHA-256 4ce0ce2914fef9bc72cfa195bc4d3f426d608433494e14401d0d4a606c649cec。用 stage-console.txt 核对设备写入状态，实机结果以本轮启动与回读日志为准。

## 实机结果

A 槽 Android 17 / SDK 37 已上线。netd1shot 执行完成，netd 持续 running，两条 stats 程序均已 pin，KernelSU shell su 成功。Android 下只读采集 bootlog 窗口，CRC 通过。到达 Android ADB 并越过原 netd1shot 阻塞。

sys.boot_completed 仍为空，system_server 重启。实机 logcat 与 tombstone_31 指向 libservice-connectivity.so 的 LocalNetEventHandler::GetRingbuf()，由于缺少 /sys/fs/bpf/netd_shared/map_netd_local_net_note_op_ringbuf 而 abort。donor netd.o 元数据定义该 ringbuf 需要内核 >=5.10，4.19 的加载器日志确认按内核范围跳过。简单调整流量统计程序的 API 门槛已解决此前故障，对 ringbuf 不能用同样的方式假定内核支持。

接手先核实 #789 是否已有兼容的 BPF ringbuf 实现，结合实际功能与 ABI 决定移植或内核回补。当前保留 Android ADB 取证，SELinux 为 permissive。完成桌面启动、正式集成和 enforcing 仍待验证。
