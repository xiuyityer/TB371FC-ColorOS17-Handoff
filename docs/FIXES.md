# 修复索引

| 领域 | 根因和最终落点 | 证据与可读实现 |
| --- | --- | --- |
| C17 早期启动 | C17 镜像使用 EROFS，4.19 需提前装载兼容模块。SELinux policy 仍 Permissive，VINTF 补齐 30.0 映射与 VNDK 30 APEX 声明后消除启动弹窗。 | [0003](../worklog/runs/0003-c17-bootlog/REPORT.md) · [0004](../worklog/runs/0004-c17-selinux-permissive/REPORT.md) · [0013](../worklog/runs/0013-c17-vintf30/REPORT.md) |
| netd 与 LocalNet | 先处理 4.19 的旧流量 BPF loader 版本门槛，再在 #789 补齐 ringbuf mmap/poll、output 与 reserve/submit/discard，连同 C17 ring map 对象的内核门槛调整。 | [0005](../worklog/runs/0005-c17-netbpfload-r2/REPORT.md) · [0008](../worklog/runs/0008-c17-netd-stats-compat/REPORT.md) · [0010](../worklog/runs/0010-c17-ringbuf-kernel/REPORT.md) · [最终内核补丁](../kernel/final-kernel.patch) |
| 工程服务、Wi-Fi、QSPM 与 GPU | 避免 Engineering 服务阻塞，处理旧 Wi-Fi HAL 返回空 radioStats、QSPM 服务等待及 GPU PreCache 早期未就绪。启动修复写入 system / system_ext。 | [0011](../worklog/runs/0011-c17-engineer-fw-compat/REPORT.md) · [0012](../worklog/runs/0012-c17-cold-boot/REPORT.md) · [0014](../worklog/runs/0014-c17-remote-audit/REPORT.md) |
| 音频、原生笔与旧模块 | 四扬声器旋转将 Android rotation 翻译为 Lenovo gsensor_rotation。笔逻辑由 init 启动，B 站双窗写入原生配置，AI 有原生命令入口。旧调度、隐私实验未迁入。 | [0015](../worklog/runs/0015-c17-native-features/REPORT.md) · [0016](../worklog/runs/0016-c17-module-regression/REPORT.md) · [原生启动配置](../overlays/native-features/) |
| 相机与投屏 | ZUI 相机是已验证的用户态替代品。投屏修复 ODMF decoder 的字段引用，按实际 Surface 选择路径，启动时只读绑定补丁 JAR。 | [0017](../worklog/runs/0017-c17-camera-connect/REPORT.md) · [ODMF 补丁脚本](../worklog/runs/0017-c17-camera-connect/patch-c17-odmf.py) |
| 通信共享 | C17 供体双路 AIDL 服务与 ovnet，进程私有 libc++，补 subscription 能力、限制 IMS 回调和排除实体卡误判。最后补虚拟数据 attach 预算、DMTP 登记路径和远端 slot 边界，解决连接后无流量。 | [C16 对照](../worklog/runs/0018-c16-sharing-reference/REPORT.md) · [0019](../worklog/runs/0019-c17-virtual-provider/REPORT.md) · [0020](../worklog/runs/0020-c17-shared-data/REPORT.md) |
| 解锁后只有 120 Hz | my_product 的桌面和系统应用高档策略仍走 120 Hz。调整目标系统应用映射和 Launcher Activity，手写笔服务继续快照用户档位，临时锁 120 Hz 后恢复。 | [0021](../worklog/runs/0021-c17-pen-refresh/REPORT.md) · [笔源码](../pen-refresh-bridge/src/pen-refresh.c) |
| 完整清刷 | 两平台先确认 WIPE，写原版 TWRP、全量 super、boot_a，清 userdata 与 metadata，设置 A 槽。 | [0022 整块回读](../worklog/runs/0022-c17-line-flash/readback-sha256.txt) · [0023 实机记录](../worklog/runs/0023-c17-clean-install/REPORT.md) |

历史日志在对应运行目录，二进制文件名是来源或输入指纹。此处提供可公开的文本摘录。TWRP 定位时优先保留故障现场，读取 pstore/tombstone/早期启动记录，再判断当前失败发生在内核、init、system_server 或首次设置阶段。
