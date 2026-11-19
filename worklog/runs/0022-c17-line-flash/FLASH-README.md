# 联想 TB371FC C17 + KernelSU 线刷包

适用于已解锁的联想 TB371FC（Fastboot 产品名 spinel），以本项目已验证的底包固件为基线。包内是 2026-11-18 确认的 C17 A 槽版本，含 4.19.325-perf+、KernelSU UAPI 6 和原版 TWRP 3.7.1_12-0。刷机会写入 recovery_a、super、boot_a，然后选择 A 槽。

super 包含 13 个 A 槽逻辑分区。完整线刷会替换原动态分区布局，覆盖原有 B 槽在 super 中的系统内容。脚本保留用户数据。首次从其他 ROM 迁移的用户数据兼容性需另行验证。

## 刷入

1. 完整解压到可写目录，安装 Python 3。Windows 和 macOS 随包提供 Android Platform-Tools；Linux 需在 PATH 中提供 Fastboot 和 ADB。
2. 把平板接到电脑并重启到 Bootloader Fastboot。正常系统已授权 ADB 时，可先执行 `adb reboot bootloader`。
3. 在解压目录执行以下命令之一。离线校验文件可加 `--check`。

   | 系统 | 命令 |
   | --- | --- |
   | macOS | `./flash-macos.command` |
   | Windows | `flash-windows.cmd` |
   | Linux | `python3 flash.py` |

4. 脚本校验镜像、机型、解锁状态和分区尺寸，刷完重启。加 `--recovery` 可启动刚刷入的 TWRP。连接多台设备时使用 `--serial` 指定目标。
5. 如果 USB 中断，回到 Bootloader Fastboot 后，在原目录为同一设备重新运行原命令并加 `--resume`。进度保存在 flash-state。若期间另行刷过任何目标分区，使用 `--restart` 从第一块重刷。

## 应用与设置

- 匹配的 KernelSU 管理器为 apps/KernelSU-32720.apk，可通过 ADB 或平板安装器安装。
- 已安装的 ZUI 相机会随用户数据保留。首次使用时安装 apps/ZUI-Camera.apk，确认相机能预览后可在应用管理中停用 ColorOS 相机，或执行 `adb shell pm disable-user --user 0 com.oplus.camera`。
- 显示设置选高刷档后，桌面和主要系统界面可用 144 Hz。原生笔服务在检测到笔接近时临时切到 120 Hz，笔离开后恢复此前刷新率模式。
- 分区及文件校验值见 manifest.json。
