# TB371FC 4.19.325 内核

基线为 smith-dog/kernel-tb371fc 的 c3df39c507c11eebb124224bd34e3ab701b6d1f3，配套发布 v2.2 / #789。仓库内的 final-kernel.patch 从实际构建源码与该提交的完整源码归档逐文件比较生成，涵盖最终 BPF map 文件操作、ringbuf copy 与 zero-copy producer、verifier 状态和 Darwin 编译兼容修改。早期实验补丁的来龙去脉仍保留在 run 0009。按内核原许可保留 COPYING。

```sh
git clone https://github.com/smith-dog/kernel-tb371fc.git
cd kernel-tb371fc
git checkout c3df39c507c11eebb124224bd34e3ab701b6d1f3
git apply --check /path/to/handoff/kernel/final-kernel.patch
git apply /path/to/handoff/kernel/final-kernel.patch
```

实际构建使用 Android NDK r27d Clang/LLD、GNU sed 4.9 和 OpenSSL 3.5.9。大小写敏感的工作树是依赖。使用 [最终 Kconfig](config-build) 初始化输出目录中的 .config。将 CONFIG_EXTRA_FIRMWARE_DIR 指向本机核验过的两份 TFA 固件所在绝对目录，再执行 [Darwin 构建命令](../worklog/runs/0009-c17-kernel-ringbuf/build-kernel-image.sh) 的等效流程。路径需按本机修改。cfg 中固件目录已改成可迁移的占位路径。

固件来自同一上游 v2.2 / #789 发布 boot 内的 builtin_fw 数据，名称、偏移、长度和哈希见 [固件来源](provenance/published-789-builtin-fw/manifest.json)。从指定 boot 解包 Image，再按该清单提取并核对，偏移从解包后的 Image 起算。当前清刷包可以直接提取已验证的 boot_a，因而不需要为普通系统分区迭代重新编译内核。

新 boot 要保持 Lenovo 机型的 DTB、ramdisk、Boot Header 及既有 KSU UAPI，并按 [run 0010](../worklog/runs/0010-c17-ringbuf-kernel/REPORT.md) 复测 EROFS 模块 CRC、BPF ringbuf 事件和设备启动。测试机 bootloader 对 fastboot boot 返回 unknown command。局部临时启动失败时，明确记录并按已授权的分区写入流程验证。
