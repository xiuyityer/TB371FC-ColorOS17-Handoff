# C17 桌面和手写笔刷新率

测试设备为联想 TB371FC（spinel，DEVICE_SERIAL），C17 A 槽，内核 4.19.325-perf+。用户把笔放远，仅用手指锁屏和解锁，确认故障表现为锁屏可到 144 Hz、进入桌面后停在 120 Hz。

## 定位及改动

- 设备最初保存的 ColorOS 刷新率档位是 8，系统峰值为 185 Hz。本机面板只枚举 30、60、120、144 Hz。已把设备用户 0 的高刷选项恢复为 4，峰值写为 144.00002 Hz。单独恢复设置后，用户仍能复现桌面 120 Hz。
- 原镜像在 `/my_product/etc/refresh_rate_config.xml` 为 `com.android.launcher` 配置了 `3-2-2-3`。只把最高档映射从 3（120 Hz）改到 4（144 Hz）。保留全局最高档 4、手写笔档 3，以及其他桌面档位和应用规则。
- 使用 [构建脚本](build-my-product.py) 从 run 0015 已安装镜像重压缩单个 EROFS 区段。新 XML 完整读回与预期一致，镜像通过 fsck.erofs。原版 TWRP 3.7.1 校验通过，写入 `my_product_a 镜像`（历史文件） 并两次整块读回匹配。来源、目标哈希及大小见 `分区清单`（历史文件），实机写入见 `flash.log`（历史文件）。

第一版运行后，返回桌面的切换动画可以到 144 Hz。窗口进入稳态后，ColorOS 仍为 Launcher 和设置等窗口投票 120 Hz。用户也确认第三方应用可到 144 Hz，手写笔在第三方应用里的降档与恢复正常。

## 固化版本及实机验收

第二版调整桌面、设置、无线设置、联系人等 20 个系统界面的高刷映射，并为 Launcher activity 写入明确规则。ColorOS 的用户档 3 与 4 共用窗口策略索引 3，笔服务仍通过峰值、最低刷新率及优选显示模式投票将面板临时切到 120 Hz。保留 60 Hz、自动档、投屏及媒体专用规则。

- [构建脚本](build-my-product-system-ui.py) 从 run 0015 镜像构建，EROFS 校验通过。
- `分区清单`（历史文件） 和 `TWRP 刷入及回读`（历史文件） 显示 my_product_a 的 SHA-256 为 40e8ce36c6ece0d11ca7860d37eee41bb289f6ded31f2df6c887f38dd8d70b56。Fastboot 从 A 槽启动，Android 读到新规则和笔服务。
- [窗口投票](system-ui-policy.txt) 显示 Launcher 和系统设置已选索引 3 对应的速率 4。[设备时间线](system-ui-timeline.txt) 显示桌面与设置达到 144 Hz，笔接近期间桌面到 120 Hz，笔离开后恢复 144 Hz。[笔服务记录](system-ui-pen.txt) 为 RESTORE reason=pen_left rc=0。
- 用户确认问题已解决。其余改动覆盖的应用未逐一测试。
