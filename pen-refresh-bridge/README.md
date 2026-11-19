# TB371FC 手写笔自动刷新率兼容

日常保留原刷新率（可为 144 Hz），检测到笔时自动切到 **120 Hz**，笔离开约 2.2 秒后恢复原设置。**这不是显示 144 Hz 与手写同时运行的修复。**

适用范围：当前 TB371FC / spinel、#50 内核和 ColorOS 16 R5、设备所有者用户 0、Magisk 31.1。此模块不改 boot、super、触控固件、面板寄存器或 SELinux 策略。

v0.4.1 修正 ROM 自带 `R94RefreshPolicy.floor` 遗漏 120 Hz 的问题：通过 Magisk 覆盖框架 JAR，只修改项目自有辅助方法，保留其他 DEX 方法与 JAR 成员，并同步 r91 启动脚本的对应哈希及清单。它不是重新刷写系统镜像；禁用或移除模块并重启可撤销覆盖。安装严格核对框架基线 SHA。

## 安装与控制

在 Magisk 的模块页从本地安装 `dist/TB371FC-Pen-Auto120-v0.4.1.zip`，重启生效。模块名为“TB371FC 手写笔刷新率兼容（自动 120 Hz）”。可用 Magisk 开关禁用，或移除后重启。

有 root 的命令行也可以立即停用并恢复当前设置：

```sh
su -c '/system/bin/sh /data/adb/modules/r94_pen_refresh_bridge/control.sh stop'
```

重新启用：将上面的 `stop` 换成 `start`。查看状态：换成 `status`。

## 工作方式

原版 144 Hz 下，固件在检测到笔后发出扫描码 606，但系统缺少消费这个通知的适配，未进入笔模式。实机采集中收到 1414 次检测通知，笔尖事件为零。120 Hz 实笔可用。

组件独立监听 NVTCapacitiveTouchScreen 与 NVTCapacitivePen，不独占、不吞掉也不伪造输入。实际检测通知、真实笔接近/落笔及启动时已有笔状态均可接管会话，即使当时已经是 120 Hz。会话同时选择 ColorOS 原生 120 档和通用刷新限制，防止设置页/回桌面时策略覆盖。笔离开后恢复先前的 min/peak/user-preferred/原生档位。会话中另选高刷新率会记为离笔后的恢复目标；另选 60 Hz 则释放兼容限制并尊重该选择。

空闲时阻塞等待输入和模块状态变化；仅会话期间每 250 ms 读取一次笔状态。合并连续检测通知，不对每个通知重复切屏。熄屏、进程正常退出、模块禁用或移除时释放临时设置；写入前保存恢复记录，异常退出后在下一次启动时恢复尚未释放的自有设置。日志及恢复记录在 `/data/adb/r94_pen_refresh_bridge`。

这套恢复依赖组件或其卸载脚本有机会执行。如果在外部强制删除模块且遗留临时 120 Hz，可使用保留的同版本 `pen-refresh --restore MODULE_DIR /data/adb/r94_pen_refresh_bridge` 恢复；不要删除 checkpoint 来冒充已恢复。

模块结构依据 [Magisk Developer Guides](https://topjohnwu.github.io/Magisk/guides.html)。没有 Zygisk 注入或权限策略扩展。停用命令立即恢复刷新设置，框架覆盖在重启后撤销。

## 构建

```sh
python3 build.py --zig /absolute/path/to/zig
```

要求 Zig 0.13.0。框架补丁生成见 `patch_refresh_policy.py`，需要精确的本机框架及校验链输入；不会从其他设备获取框架替换。其同长度字节码修改经过重新解析及 23 个有限值、非有限值和档位边界检查，源代码等价实现见 `src/R94RefreshPolicy-floor.java`。

仅重新打包已有二进制：`python3 build.py --package-only`。ZIP 成员逐一 SHA 与 CRC 校验，输出载荷清单和 ZIP SHA。静态链接的 musl 及工具链运行库许可见模块内 THIRD_PARTY_NOTICES。

## 验证范围

2026-11-17，原版 #50 boot 上两次实际靠近/书写/移开：144 → 120 → 144 均被显示模式采集确认，记录到 919 行 ABS_X 和 5 次 BTN_DIGI DOWN，用户确认画面与书写正常。详细归属与日志在 `../analysis/pen-144hz/bridge-pilot-20261117/`。

该结果覆盖本次实笔和自动恢复，不代表已测尽所有应用、所有笔型号或长期待机。先前直接把 B3 40 放到 144 Hz 的内核候选导致黑屏与线条，已经撤回；本模块不包含那项改动。

上述基础验收属于 v0.1.0；随后用户发现“用笔打开设置、手指滑动设置、用笔上滑回桌面”会回到 144 Hz 并失去笔输入。临时 v0.2.0 仅增加原生选择器仍未修复；未将其作为可用版本发布。v0.4.1 新增 120 Hz 框架过滤修正，验收结果以版本对应交付记录为准。

v0.4.1 还将 `/my_product/etc/refresh_rate_config.xml` 的 `ipePencilRateId` 从 4（144 Hz）修正为 3（120 Hz），保留日常默认 144 Hz。该单文件只读绑定在 system_server 启动前完成；会话期间同步原生 `settings_enable_oppo_pencil`，使 ColorOS 自己向 SurfaceFlinger 下发笔用 120 Hz，而不只依靠 DMS 通用设置。禁用并重启会撤销此绑定。

最终保留版本为 v0.4.1：设置页手指滑动与笔回桌面的混合输入回归已获用户确认。完整方法、失败记录、验收范围及回退步骤见 [FIX-RECORD-20261117.md](FIX-RECORD-20261117.md)。
