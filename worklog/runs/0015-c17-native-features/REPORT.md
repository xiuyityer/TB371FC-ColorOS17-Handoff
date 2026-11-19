# Run 0015 · 手写笔刷新率与 C16 模块原生集成

设备 DEVICE_SERIAL，TB371FC/spinel。A 槽继续运行 run 0013，boot ID `REDACTED`，system_server PID 1857，启动完成、动画停止。未重启或写入分区。

## 手写笔

复用已在 C16 用户回归通过的 v0.4.1 源码，以 Android NDK 编译 arm64。C17 实机独立运行确认打开 NVTCapacitiveTouchScreen 与 NVTCapacitivePen，进入阻塞等待，收到 TERM 后正常退出。旧 C16 JAR 不参与构建。C17 成对镜像通过原生 init 服务 `c17_pen_refresh` 在 boot_completed 后启动，恢复中断的会话后根据已有高刷档设置无笔基线。用户显式 60 Hz 选择保留。状态和日志在 `/data/misc/c17-pen-refresh/`，其中 `disable` 文件可让本机服务退出并恢复笔会话保存的设置。

实机已用可恢复的刷新率设置探针确认 120 Hz 锁帧，当前旧配置下设置 144 Hz 时 SurfaceFlinger 物理候选范围到 144 Hz，但渲染上限和实际 active mode 仍为 120 Hz。C17 Oplus 框架有相同的 XML 字段及 my_product 加载路径，候选在原 XML 中设 `defaultMaxRate=144`、`maxrefreshsettings=4`，保留 `ipePencilRateId=3` 和其他应用策略。还需要从新镜像冷启动后用实体笔观察 SurfaceFlinger 的 144→120→144。远程设置探针已恢复原值，空首选项从 -1 -1 0.0 规范化为 null。

## C16 交付中的四个模块

| C16 模块 | 用途 | C17 结论 |
| --- | --- | --- |
| r94_ai_transaction_candidate | 对七个固定包做可恢复的停用，保留之前状态 | C17 SDK 37 令旧 SDK 36 脚本拒绝运行。六个存在且均已停用，一个缺失。移植为 `/system_ext/bin/c17-ai-controls status\|disable\|restore`，默认不自动改包。现机已验证状态查询、跳过已停用和缺失的包、无待恢复记录时安全返回。需要对初始启用的包单独验证真实切换与恢复。 |
| r94_bili_native_rules | 哔哩哔哩可拖动双窗、默认比例、直播例外及旧原生配置更新维护 | C17 已含同名原生 XML 及 B 站条目。只合并 B 站拖动、比例和全屏/重开例外，保留 C17 现有 MainActivityV2、登录页和其他应用规则。两个工厂 XML 版本各加一，不部署旧 Magisk DEX。实机未装 tv.danmaku.bili，需验收双窗、直播和云规则更新。 |
| r94_foreground_schedtune | 控制 C16 ROM 内置 mapper/原生前台调度器的开关 | C17 缺少服务和 mapper，`/dev/stune` 未挂载。虽然内核注册 schedtune 控制器，不能直接启用这份旧控制器。未加入镜像。 |
| r94_speaker_direction | 跟随屏幕方向调整四扬媒体声道并在通信或停用时归还路由 | C17 内核与固件布局不同。实机缺少要求的 `TB371FC Route State` 和 `TB371FC Route Request` ALSA 控件。API 19 兼容需要音频驱动侧实现和实听，未加入镜像。 |

本表以 C16 R5 的 module-delivery-closure.txt 四项为范围。另有独立的隐私密码测试项，不属于这份四项清单。

## 镜像与验收边界

- `my-product-a-native.img`，2,570,592,256 字节，包含笔配置和两个 B 站 XML。
- `system-ext-a-native-slot.img`，928,116,736 字节，包含原生笔服务、AI 命令及 run 0014 的依赖集成。
- 使用 run 0014 的 `system-a-integrated.img`，954,871,808 字节，和上述两张镜像配套。精确哈希见 native-images.sha256。

my_product 全盘 fsck 及指定 XML 回读通过。system_ext 全量回读验证 3,966 个 inode 与 3,520 个文件的内容、权限、所有者和扩展属性。新增两张镜像经 4.19 实机独立命名空间只读挂载，整镜像及相关文件哈希匹配，两个 shell 入口通过设备端语法检查。测试后卸载并清理平板临时镜像。待成对写入后的冷启动、笔回归和 B 站 UI 测试。现用内核及 TWRP 保持原有版本。
