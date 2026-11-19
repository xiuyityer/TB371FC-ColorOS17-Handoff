# run 0009 · 4.19 BPF ring buffer 移植准备

设备 DEVICE_SERIAL 已确认处于 FASTBOOT。本轮没有写入设备。A 槽保留 run 0008，Android 17 已通过 netd，system_server 在 LocalNet ring buffer 初始化时重复崩溃。

## 本次验证结果

- 从 #789 发布 boot 的 IKCONFIG 提取实际配置。其与提交 c3df39c507c11eebb124224bd34e3ab701b6d1f3 的 config-v2.2.txt 在换行归一后相同。保留 BPF_SYSCALL、BPF_JIT_ALWAYS_ON、MODVERSIONS 等原设置。
- 上游 BPF mmap 和 ringbuf 补丁均无法直接应用。baseline/ 中参与检查的源码已逐文件与该提交的 Git blob SHA 核对。
- donor-ringbuf-calls.tsv 记录实际 donor BPF 对象的 map relocation 和 helper 调用。新版统计程序使用 reserve/submit，带 loopback 的版本也使用 discard。现有实机通过的 4.19 stats 版本没有 ringbuf producer。
- 0001-bpf-map-file-ops-review.patch 添加 map mmap/poll 回调接口，保留老 map 的默认行为，阻止把初始只读映射升级为可写。补丁通过 git apply --check。原始和改后的 syscall.c 均使用同一组 #789 已准备头文件编译成 AArch64 对象。此检查覆盖文件接口编译，尚未链接内核。verifier 引用跟踪的上游前置补丁也已取回，对当前 verifier.c 的 apply check 失败，需按 #789 的状态结构适配。
- 已在本机安装官方 Darwin NDK r27d 工具链并构建静态 AArch64 probe-ringbuf-arm64。探针依次验证 map create、map info、消费者及生产者映射、生产者页写入限制、mprotect 限制和空 ring 的 poll。后续在真实候选内核上执行，事件收发还需单独验证。
- 旧网络下源码下载的三次 180 秒尝试分别只收到约 22 MiB、0 B、3.3 MiB。用户换网后以 HTTP/1.1 重试，HTTP 200，首字节 2.88 秒，共 197,752,103 字节，耗时 225.52 秒，平均 876,876 B/s。旧传输有明显停顿，但无法凭 curl 日志精确归因到线路、代理或 GitHub 节点。重试完整包通过 gzip -t，SHA-256 见 kernel-source.sha256。
- 完整源码已解包到 case-sensitive APFS 的 kernel-build-volume/kernel-v2.2。关键 BPF 源文件与 Git blob 核对过的基线逐字节相同，仓库 config-v2.2 与归档一致。按 #789 的原配置完成 olddefconfig，仅适配 Clang/LLD 探测配置。

## 完整源码构建检查

Darwin NDK Clang 18 + LLD 已在完整源码上通过 Kbuild 编译 kernel/bpf/syscall.o 和 kernel/bpf/verifier.o，输出均为 AArch64 relocatable ELF。原始 BPF 源文件已核对，编译使用 host ELF 头、ARM64 UAPI 头及本机构建的 OpenSSL libcrypto；darwin-clang-inline-lse.patch 只调整 Clang 内联汇编的 LSE 指令声明。复现入口为 prepare-full-source.sh 和 build-baseline-object.sh。验证结果见 full-source-baseline-kbuild.log。

verifier-reference-trial/ 是只用于查看上游补丁冲突的副本，其中有未应用的 hunk，不能作为完整实现使用。

## ring buffer map 已接入完整源码

- 完整源码上依次应用了 0001-bpf-map-file-ops-review.patch、0002-bpf-ringbuf-map-review.patch、0003-bpf-ringbuf-map-helper-guard.patch。原版 boot 镜像及设备分区未写入。
- Map 参考 [Android common 5.10 固定源码](https://android.googlesource.com/kernel/common/+/21d85af22b5c6677ca6d2f9bd71ccc634a9c2554/kernel/bpf/ringbuf.c)。保留 UAPI map type 27、重复映射的数据页、只允许消费者页写入和 poll 接口。计费使用 4.19 现有 memlock 机制，创建限制为 CAP_SYS_ADMIN。当前 verifier 拒绝将 ringbuf map 传给 BPF helper，直到接入可验证的 producer。
- Kbuild 成功编译 patched syscall.o、verifier.o、ringbuf.o，见 ringbuf-map-guard-kbuild.log。map 暂无实际事件 producer，未实机运行 probe。
- 首次整内核编译因 BSD sed 生成的 AppArmor 能力表不完整失败。已本机编译 GNU sed 4.9，第二次已重生成正确的能力表，随后发现 #789 配置中的原作者固件目录不存在，并遇到 rmnet 的旧式声明编译错误。该次已结束，见 ringbuf-map-image-gnu-sed.log。即使 Image 成功产出，此阶段仍缺 verifier 引用跟踪和 ringbuf helper，不能视为 C17 开机修复。

## 复制式 producer 与整内核构建

- 0004-bpf-ringbuf-copy-producer.patch 从同一固定 Android common 实现接入 `ringbuf_output` 和 `ringbuf_query`，通过 cgroup skb 的 helper 表公开。两边都校验 helper 与 map 类型。保留 UAPI helper 130–134 的编号，reserve/submit/discard 在 verifier 上仍不可用。
- 完整源码的 syscall.o、verifier.o、ringbuf.o 和 net/core/filter.o 均通过 ARM64 Kbuild。输出符号见对象文件，日志见 ringbuf-copy-producer-kbuild.log。
- probe-ringbuf-events-arm64 支持 --events，加载一个只对私有 ring map 输出固定样本的 cgroup skb 程序，用 BPF_PROG_TEST_RUN 执行，验证 poll、事件内容、双映射别名和消费。该 probe 已通过本机交叉编译，尚未实机执行。
- published-789-builtin-fw/ 保存从验证 SHA 的官方 #789 boot 提取的两份 TFA 固件。按原 Image kallsyms 的 builtin_fw 表及 AArch64 RELA 确认两个条目的名字、数据和长度。YC 同仓库内副本逐字节一致。对象目录配置仅把 EXTRA_FIRMWARE_DIR 改为本地目录，固件列表保持原样。
- darwin-clang-rmnet-prototype.patch 为无参函数定义补 void，修复 Clang 18 的 strict-prototypes 构建错误。随后已重新发起完整 Image 构建，见 ringbuf-copy-producer-image.log（执行会话 9194）。
- 设备保留 FASTBOOT，未写入分区。复制式 helper 用于验证 ring buffer 事件路径，donor 仍需 zero-copy reference tracking 和相应程序兼容处理。

## 下一步

在 #789 基线上适配 ringbuf 分配、内存计费及回收，核对 mmap 页布局和 BPF UAPI 固定编号。按实际 producer 所用 helper 回补 verifier 引用跟踪、内存边界、分支状态合并和引用释放校验，再核对 BPF 程序所需的其余 map 与 helper。用完整构建产物核对 KernelSU、EROFS 与 C16 vendor 模块的符号 CRC，然后在实机上验证 map、事件收发和 C17 完整启动。当前对象仅为编译验证的局部改动，尚无可刷 boot 候选。

参考源码：
- https://github.com/torvalds/linux/commit/fc9702273e2edb90400a34b3be76f7b08fa3344b
- https://github.com/torvalds/linux/commit/457f44363a8894135c85b7a9afd2bd8196db24ab
- https://github.com/torvalds/linux/commit/fd978bf7fd312581a7ca454a991f0ffb34c4204b
