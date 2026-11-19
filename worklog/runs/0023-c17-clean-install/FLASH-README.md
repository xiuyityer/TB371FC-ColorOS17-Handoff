# 联想 TB371FC C17 + KernelSU 全量清刷包

适用于已解锁的联想 TB371FC（Fastboot 产品名 spinel），沿用本项目已验证的联想底包固件。包内含 C17、KernelSU UAPI 6、4.19.325-perf+ 内核和原版 TWRP 3.7.1_12-0。

这是一键清刷包。选择继续会清除平板内部的应用、照片、文件和当前账号状态。原先使用 B 槽动态分区的 ROM 也会随整个 super 覆盖。刷机前请保存需要的文件。

## 一键刷入

1. 用系统解压工具或支持 ZIP64 的解压工具完整解包。Windows 如未识别平板，请先安装 Android Bootloader Interface 驱动。
2. 连接 USB 数据线，把已解锁的平板进入 Bootloader Fastboot。可在已授权 ADB 的系统中执行 `adb reboot bootloader`，或使用平板的实体按键进入。
3. 运行对应的一键脚本。Windows 和 macOS 已各自附带 Fastboot，脚本使用系统自带的环境执行。

   | 系统 | 入口 |
   | --- | --- |
   | Windows | 双击 `flash-windows.cmd` |
   | macOS | 双击 `flash-macos.command`，也可在终端运行 `./flash-macos.command` |

4. 脚本首先显示清除数据提示。只有输入 **WIPE** 并回车才会继续校验镜像和设备。直接回车或输入其他内容立即退出。
5. 刷写原版 TWRP、完整 super 和 C17 启动镜像。清除 userdata 与数据加密使用的 metadata，切到 A 槽并自动重启。第一次开机请在平板上完成语言、网络、账号等设置。
6. USB 中途断开时，重新进入 Bootloader Fastboot，保持同一解包目录，用下列命令续刷。续刷同样要求确认。期间如果另外刷过目标分区，请从头开始。

   | 操作 | Windows | macOS |
   | --- | --- | --- |
   | 续刷 | `flash-windows.cmd -Resume` | `./flash-macos.command --resume` |
   | 从头开始 | `flash-windows.cmd -Restart` | `./flash-macos.command --restart` |
   | 离线核验 | `flash-windows.cmd -Check` | `./flash-macos.command --check` |

## 进入桌面后

- 显示设置选择高刷新率档。桌面和主要系统界面可使用 144 Hz。手写笔接近时暂时切到 120 Hz，移开后恢复高刷。
- 可从 apps 目录安装匹配的 `KernelSU-32720.apk`。需使用 ZUI 相机时，安装 `ZUI-Camera.apk`，确认预览正常后可在应用管理中停用原相机。
- APK 可以复制到平板后使用系统安装器安装。如果使用 ADB，先在平板开发者选项打开 USB 调试并确认本机授权，然后使用包内 tools 目录的 ADB 安装。

APK 的复制安装、ADB 命令和高刷设置见 [首次开机与应用安装](FIRST-BOOT.md)。
