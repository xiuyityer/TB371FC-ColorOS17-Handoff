# run 0010 · 实机验证 4.19 ring buffer

Mac 上完整编译了 #789 补丁树，修正 vendor 音频头文件的失效绝对链接及两处 Qualcomm 旧式无参声明。先后链接复制式及零拷贝内核，最终 Image SHA-256 为 5f9e77e8cf71b0d9a926af9ad06b22de8dc205db632bc251cec1fbecaaa1d21c。0005/0006 补丁涉及路径状态、空分支和别名失效，拒绝带未释放引用退出、tail call 或跨 BPF 子程序调用。现阶段约束为固定指令偏移的记录访问，donor 的完整程序仍需适配。

- 新 EROFS 150/150 和随 #789 发布的 KernelSU 216/216 CRC 一致。vendor 模块不匹配均已存在于旧 #789。
- 新 boot 保留原 DTB、KSU、日志器和 permissive 配置。Fastboot 临时 boot 返回 unknown command，随后明确刷入 boot_a 并从 A 启动。运行内核为 4.19.325-perf+ #2。
- 静态 API 28 探针因 Bionic TLS 对齐不足退出。换动态 API 35 PIE 后，--events、--submit、--discard 三项实机均通过，验证 map 创建、读写保护、事件与双映射及消费。KSU shell su 通过。
- 将 donor netd.o 的 LocalNet、loopback 两条 map 内核下限由 5.10 调整为 4.19，设备对象哈希一致。重启后两个 map 均成功 pin，system_server 越过 LocalNet abort，进入 phase 480。继续沿用 4.19 流量统计程序，donor 的完整流量事件产出仍未验证。当前 overlay 依赖 /data。
- phase 480 的新阻塞为工程服务 vendor.oplus.hardware.engineer.IEngineer/default 不存在。watchdog ANR 主线程卡在 OplusEngineerFwService.getEngineerService；对应 DEX 现有 null 回退，onBootPhase 仅在服务存在时尝试读取后盖色号。
- 把该处 waitForService 换为 checkService，临时 bind mount 到 init 的命名空间并重启 Zygote。验证 Zygote 看到修改后的 JAR，system_server 日志进入启动用户 0。随后 USB 连接断开，下一次 Android 上线时旧 JAR 恢复，尚未验证桌面。
- 将同一单点修改打包到固定尺寸的 system 镜像。仅改三个 EROFS 数据 extent，fsck 通过，目标 JAR 回读逐字节一致。实机持久测试见 run 0011。

新版 donor BPF 流量对象还依赖 sk_storage_get、sk_fullsock、ktime_get_boot_ns。在最新版 egress 中还使用 sk_lookup_tcp/udp 与 sk_release。见 producer-dependencies.tsv，应按实际依赖逐项处理。
