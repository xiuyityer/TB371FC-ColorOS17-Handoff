# Lenovo TB371FC · ColorOS 17 移植交接

当前基准是 **2026-11-18 C17 + KernelSU 全量清刷版**。设备为联想 TB371FC，Bootloader 产品名 spinel，运行 C17 A 槽，供体指纹为 OnePlus OPD2413，内核为 4.19.325-perf+。项目在本版暂停。

| 要做什么 | 入口 |
| --- | --- |
| 从保留的清刷 ZIP 恢复原样工作镜像 | [恢复基准](docs/RESUME.md) |
| 查每项修复的原因、落点和失败路线 | [修复索引](docs/FIXES.md) |
| 重建 4.19 内核 | [内核来源、最终补丁和配置](kernel/README.md) |
| 冷启、线刷和首次设置 | [刷机说明](worklog/runs/0023-c17-clean-install/FLASH-README.md) · [应用安装](worklog/runs/0023-c17-clean-install/FIRST-BOOT.md) |
| 实机验收、复现边界和待办 | [交接记录](docs/VALIDATION.md) |

仓库存放修复方法、源码改动、21 份历史报告、刷机入口及关键日志摘录。日志已移除设备及网络识别信息。更新基准时，请在新运行目录记录镜像 SHA-256、目标分区、实机读回和验收范围。

分区镜像、APK、厂商固件、工具链与全量设备日志由持有者保存在本地。继续开发优先使用维护者保留的清刷 ZIP，GitHub 的 Source code ZIP 只包含此仓库文件。该清刷版会重写整个 super 和 A 槽启动 / 恢复镜像，确认 WIPE 后会清除 userdata 与 metadata。

## 上游

- [C16 移植过程及底包构建](https://github.com/Qinyibo/TB371FC-ColorOS16/tree/0ab807e9fcbedff589fe9261ed204dc6103e5b9d)
- [联想内核源码参考](https://github.com/Qinyibo/android_kernel_lenovo_tb371fc)
- [第三方 #789 / KernelSU 内核基线](https://github.com/smith-dog/kernel-tb371fc/tree/c3df39c507c11eebb124224bd34e3ab701b6d1f3)
- [TB710FU 的 C16 修复取证参考](https://wasddestroy.site/tb710fu-doc/generic/flash_fix_module_yu_c16.html)
