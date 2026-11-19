# 设置页手指滑动后，笔回桌面失效：修复记录

## 最终状态

2026-11-17，保留的版本为 **v0.4.1**。用户按“桌面用笔打开设置 → 手指滑动设置 → 用笔上滑小白条返回桌面并继续操作”复测后确认“这次正常了”。

当前设备使用同一版本的后台程序，原版 #50 boot 保留。日常为 144 Hz，笔会话为真实 120 Hz；这仍不是 144 Hz 与笔输入同时运行的方案。

## 问题与证据

1. v0.1.0 只依赖扫描码 606 开始会话，只改 min/peak/首选模式。在故障现场，这些设置均为 120，但实际显示仍为 144。
2. 进一步抓取发现，DisplayModeDirector 已请求 120 Hz，而 SurfaceFlinger 的实际 `displayManagerPolicy` 被另一层原生策略设为 144 Hz。因此不能用“设置值是 120”代替实际模式验收。
3. ROM 自带 `R94RefreshPolicy.floor` 只分 30/60/144 三档，将 120 请求归为 60。v0.3.0 补上了 120 档，但单独这项修改仍未修复。
4. `/my_product/etc/refresh_rate_config.xml` 的注释写明笔专用锁帧为 120 Hz，实际 `ipePencilRateId="4"` 却对应 144 Hz。反汇编确认本系统的 ID 3 为 120、ID 4 为 144。原生策略还以 Global `settings_enable_oppo_pencil` 作为笔启用条件，而原适配未同步这条状态。
5. v0.4.0 接通原生策略后，采集已经看到 SurfaceFlinger 限制为 120，且回桌面时保持 120；随后后台程序以 `STOP result=1` 异常退出，恢复为 144，造成再次失效。
6. 输入处理存在将 `SYN_DROPPED` 和可恢复的 `EINTR` 当作致命错误的路径。v0.4.1 改为正确重同步/继续读取，并增加错误分类日志。**v0.4.0 没有记录具体退出 errno，不能把那一次退出绝对归因于某一个错误码；最终回归也没有单独触发并验收所有丢帧分支。**

## 保留的修复方法

- 在项目自有 `R94RefreshPolicy.floor` 方法中加入 120 Hz 桶，其他 OEM 方法和 JAR 成员保持原载荷。使用同长度 DEX 修改，更新 DEX SHA1/Adler32，并重新解析验证。
- 将 XML 中唯一的 `ipePencilRateId="4"` 改为 `"3"`，不改 `defaultMaxRate="144"` 或日常 `maxrefreshsettings="4"`。
- `/my_product` 在本 ROM 中不是标准 `/product` 别名，因此在模块 `post-fs-data.sh` 中，仅将这一份 XML 做只读绑定。校验基线、绑定后 SHA 及 boot_id；后台只有确认本次启动已绑定成功才运行。已核对 system_server 命名空间看到相同的新 SHA。
- 对真实笔检测、笔接近/落笔事件以及启动时已有笔状态建立会话。会话内同步原生笔启用状态、原生 120 档及通用限制，离笔/熄屏/停用后恢复此前状态。
- `SYN_DROPPED` 时保留会话，忽略不完整帧直到下一个 `SYN_REPORT`，再用 `EVIOCGKEY` 与固件笔状态重同步，不伪造输入、不独占 evdev。`EINTR` 不再作为设备失效处理。
- 框架覆盖与 r91 的 JAR 哈希检查、`apply.sh` 自身 SHA 清单一起更新，避免启动校验链不匹配。

## 文件入口

- 后台源码：`src/pen-refresh.c`
- 框架补丁生成及边界检查：`patch_refresh_policy.py`
- 框架方法的 Java 等价实现：`src/R94RefreshPolicy-floor.java`
- 原生 XML 补丁指纹：`native-config-patch-receipt.json`
- 框架修改指纹及 23 项数值边界检查：`refresh-policy-patch-receipt.json`
- 模块启动、停用与恢复：`module/post-fs-data.sh`、`module/service.sh`、`module/control.sh`
- 构建/归档与逐成员 SHA/CRC 验证：`build.py`
- 最终模块：`dist/TB371FC-Pen-Auto120-v0.4.1.zip`
- 最终交付指纹与验收：`dist/delivery-v0.4.1.json`

源码改动后用 Zig 0.13.0 构建；精确命令见 `build.py`。框架脚本只接受本机基线 JAR，不可拿其他 ROM 的框架套用。原始厂商输入仍需自行持有。

## 实机验收与范围

设备 DEVICE_SERIAL / TB371FC / spinel / A 槽。最终回归 boot_id 为 `7b9e677e-c691-4627-a9a7-1ffccecc4b15`。

回归原始材料在 `../analysis/pen-144hz/home-gesture-fix-v041/`：显示时间线、SurfaceFlinger 策略、笔事件、后台日志及恢复后设置。记录到 711 行 ABS_X、3 次 BTN_DIGI DOWN；回桌面继续用笔时显示为 120 Hz，固件笔状态为 1，后台进程存活。离笔后恢复 144 档，用户确认正常。

v0.4.0 的框架、XML 绑定及开机启动经过重启验证；v0.4.1 仅热更新后台程序和版本材料，完成上述回归，未为重复检查而再次重启。更长时间的混合操作和专门的输入队列溢出压力测试尚未验收。

失败尝试与原始日志保留在 `../analysis/pen-144hz/home-gesture-bug/`、`home-gesture-fix-v020/`、`home-gesture-fix-v030/`、`home-gesture-fix-v040/` 以及 `history/`。不要将这些版本当作最终修复包。

## 停用与回退

在 Magisk 中禁用本模块并重启，框架及 XML 覆盖随之撤销，原系统文件和对应校验链恢复。立即停用会话可执行：

```sh
su -c '/system/bin/sh /data/adb/modules/r94_pen_refresh_bridge/control.sh stop'
```

此命令恢复刷新设置；框架/XML 覆盖在重启后撤销。不需要清空数据或刷写 boot。若异常退出遗留 checkpoint，保留它并使用同版本程序的恢复入口，不要删记录来冒充已恢复。
