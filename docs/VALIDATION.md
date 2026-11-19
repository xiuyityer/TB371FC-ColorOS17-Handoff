# 实机验收边界

- 全量包的 12 GiB super、96 MiB boot_a 和写入长度范围内的原版 TWRP 各自整块哈希吻合。macOS 上实刷，首次清除 userdata 与 metadata 后到 ColorOS 欢迎页，完成初始设置进入桌面。Windows 入口语法通过，Windows USB 真机流程待测。 [回读](../worklog/runs/0022-c17-line-flash/readback-sha256.txt) · [清刷记录](../worklog/runs/0023-c17-clean-install/REPORT.md)
- 系统启动、KernelSU 32704-6 管理器 32720-6、桌面稳态 144 Hz、笔 144→120→144 Hz 已核验。清刷后若供体 UI 把高刷选成 185 Hz，按应用安装说明恢复已验证档。 [刷新率日志](../worklog/runs/0021-c17-pen-refresh/system-ui-timeline.txt) · [首次设置](../worklog/runs/0023-c17-clean-install/FIRST-BOOT.md)
- 手机投屏和通信共享曾在同一 ROM 基线上联测通过。更晚一次通信共享重拨见 0x1103，反复切换和其他手机未验收。 [共享修复与限制](../worklog/runs/0020-c17-shared-data/REPORT.md)
- ZUI 相机早期实机预览通过。新用户清刷后复验到重新安装和首次权限界面。原生 ColorOS 相机仍为已知兼容问题。 [相机记录](../worklog/runs/0017-c17-camera-connect/REPORT.md)
- SELinux 仍为 Permissive。控制中心偶发掉帧已定位到纹理上传、着色器编译相关路径，未验收最终修复。B 站规则已集成，实际应用回归待补。 [性能诊断](../worklog/runs/0016-c17-module-regression/REPORT.md)
