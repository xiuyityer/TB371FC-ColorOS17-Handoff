# 首次开机后安装应用

刷完后先在平板上完成 ColorOS 的首次设置并进入桌面。压缩包的 apps 文件夹有两份经过实机安装验证的 APK。

- **KernelSU-32720.apk** 是与包内内核配套的 KernelSU 管理器。装好后打开 KernelSU，主页应显示「工作中」。测试版本为管理器 32720-6 与内核侧 32704-6。
- **ZUI-Camera.apk** 是用于联想平板的相机。装好后打开「相机」，按安装器或系统提示允许所需权限并检查预览。如同时存在两套相机，可在设置的应用管理里停用原 ColorOS 相机。

## 直接在平板安装

先把两份 APK 传到平板的下载目录，再打开平板的「文件管理」，点开 APK 并确认安装。若 Android 要求允许从此来源安装，按提示为文件管理临时开启该权限。Windows 可将 USB 用途切换为「文件传输」后复制文件。

## 用包内 ADB 安装

先在平板开启开发者选项和 USB 调试，连接电脑并允许该电脑的调试请求。在完整解压目录执行：

Windows 的命令提示符：

```cmd
tools\windows\adb.exe install apps\KernelSU-32720.apk
tools\windows\adb.exe install apps\ZUI-Camera.apk
```

macOS 的终端：

```sh
./tools/macos/adb install apps/KernelSU-32720.apk
./tools/macos/adb install apps/ZUI-Camera.apk
```

如果 ColorOS 弹出 USB 安装确认，在平板上点允许。每一条命令完成时会显示 Success。

## 桌面刷新率

如果新装后切换高刷仍卡在 120 Hz，可以用已授权的 ADB 恢复实机验证过的 144 Hz 档。以下以 macOS 为例。Windows 终端把命令中的 `./tools/macos/adb` 换成 `tools\windows\adb.exe`。

```sh
./tools/macos/adb shell settings put secure oplus_customize_screen_refresh_rate 4
./tools/macos/adb shell settings put system peak_refresh_rate 144.00002
```
