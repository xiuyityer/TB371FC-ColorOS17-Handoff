# C17 + KernelSU 全量线刷包

## 固化的版本

设备 DEVICE_SERIAL（TB371FC / spinel），C17 A 槽。锁屏、桌面与主要系统界面的刷新率和笔逻辑来源见 [run 0021](../0021-c17-pen-refresh/REPORT.md)。通信共享沿用 run 0020 厂商镜像，投屏及原生笔服务沿用 run 0017。未引入 Magisk 或旧模块。

本轮旧包已退役并删除。当前发布版本见 [run 0023](../0023-c17-clean-install/REPORT.md)。旧包封装内容如下。
- 385 个 Android sparse 分片覆盖完整 12 GiB super，每片文件至多 32 MiB。原有几何、元数据和 13 个 A 槽逻辑分区与刷前设备逐项匹配。
- 4.19.325-perf+ 的 KernelSU UAPI 6 boot_a，以及通过指纹核对的原版 TWRP 3.7.1_12-0 recovery_a。刷入前 boot_a 的 80–84 MiB 可变日志区归零后与包内启动镜像匹配。
- APK 附件包括已验证的 KernelSU 32720 管理器和 ZUI 相机。完整线刷未格式化 userdata。该机已有的相机安装、原相机停用标记与旧模块归档状态沿用应用数据。其他设备首次使用 ZUI 相机需在开机后安装包内 APK。原生笔服务随 init 启动。
- 随包包含 macOS 和 Windows 入口，Linux 可用系统 Platform-Tools 调用同一 Python 入口。实机只运行了 macOS 路径。

源文件与映射由 [构建脚本](build-package.py) 生成。`刷前实机分区`（历史文件）、`应用与 recovery 哈希`（历史文件）、`清单`（历史文件） 保存完整 SHA-256。离线解析分片重算每个分区的字节数和哈希，校验最终 ZIP 的成员与 CRC，外部校验值见 `archive.sha256`（历史文件）。

## 适用范围

测试的是同台平板从已有 C17 的保留数据重刷。完整线刷写入整个 super，包内 B 槽逻辑分区无内容。原先的 B 槽 ROM 如依赖 super，将随布局覆盖。刷写脚本只写 recovery_a、boot_a 和 super，选 A 启动。其余底包固件沿用设备现状。跨 ROM 保留数据、首次设置、Windows 与 Linux 真机流程另行验证。从仍有 C16 旧模块的环境迁移时，先在原系统中停用同名旧模块，项目模块列表见 [run 0017](../0017-c17-camera-connect/retire-c16-modules.sh)。

## 刷写记录

[刷包输出](flash-console.log) · `设备 Fastboot 记录`（历史文件）

- Fastboot 记录为 388 步全部完成，包含原版 TWRP、385 个 super 分片、boot_a 及切换 A 槽。
- [Recovery 身份](recovery-identity.txt) 为 TB371FC、root ADB、TWRP 3.7.1_12-0。[整块回读](readback-sha256.txt) 中 super 的 12 GiB、boot_a 的 96 MiB 及 TWRP 的 69 MiB 写入范围均与包内镜像一致。
- `Fastboot 启动`（历史文件） 确认 A 槽。`Android 验收`（历史文件） 读到开机完成、动画停止、4.19.325-perf+、KernelSU root、原生笔服务正在运行。桌面焦点下实际刷新率为 144 Hz。匹配管理器及 ZUI 相机安装保留，原相机停用状态保留。完整刷包后未重测手机互联或相机预览。手写笔物理联测见 run 0021，本轮验证原服务正常启动。
- [刷机说明](FLASH-README.md) 与 ZIP 内一致。临时解包副本可从最终 ZIP 恢复。验证脚本先等系统和笔服务均就绪后才采集状态。
