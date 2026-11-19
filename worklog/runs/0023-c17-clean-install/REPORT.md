# C17 全量清刷与首次开机

## 线刷包

`全量清刷 ZIP`（历史文件） 内有 Windows 和 macOS 两个入口。Windows 双击 flash-windows.cmd，macOS 双击 flash-macos.command。两边都先要求输入 WIPE，确认后才校验并操作设备。两平台使用同一 `刷写清单`（历史文件）。顺序为原版 TWRP recovery_a、完整 super、boot_a、清除 userdata 与 metadata、选择 A 槽并重启。使用 Windows 自带 PowerShell 和 macOS 自带 sh，Fastboot 和 ADB 随包。Mac [取消测试](cancel-test.txt) 验证了其他输入和 EOF 都在建立刷机记录之前退出。Windows 入口做了 [PowerShell 语法检查](windows-syntax.txt)，Windows 主机上的实刷尚未验证。

镜像沿用 [run 0022](../0022-c17-line-flash/REPORT.md) 的实机版本，匹配当时回读的 boot_a、原版 TWRP 与 12 GiB super。本轮 Fastboot 实机重新写入这些镜像。见 [Mac 控制台](mac-flash-console.log) 和 `Fastboot 记录`（历史文件）。本轮测试的是清刷同一台已匹配底包的设备。

## 清刷后的首次设置

DEVICE_SERIAL 的 userdata 和 metadata 均由 Bootloader 确认清除。刷机前创建的 /sdcard/.c17-clean-install-marker 在 [首次开机读回](first-boot.txt) 中消失。随后开机到 ColorOS 欢迎页，用户完成语言、网络和引导，事件日志记录 CompletePage 及 Launcher，device_provisioned 和 user_setup_complete 都为 1。详见 [首次设置事件](setup-wizard-events.txt)。

- [KernelSU 管理器安装](install-ksu.txt) 与 [ZUI 相机安装](install-camera.txt) 均返回 Success，用户确认装好。管理器主页显示工作中，内核接口为 32704-6，管理器为 32720-6。
- 新用户的亮屏高刷设置可能写入供体的 185 Hz 档。使用原生设置键切回本机 144 Hz 后，[桌面实机](desktop-144.txt) 的实际显示模式为 144 Hz，原生笔服务运行。上一轮同一镜像已完成手写笔悬停测试。
- 随包 apps 目录有两份 APK。进入桌面后可复制到平板用文件管理器安装，也可使用包内 ADB。对应 Windows 与 macOS 命令见 [首次开机与应用安装](FIRST-BOOT.md)。

[刷机说明](FLASH-README.md)
