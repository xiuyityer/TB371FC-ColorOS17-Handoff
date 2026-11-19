# Run 0018 · C16 通信共享参考核对

## TB710FU v4.0.1

刷入指南适配 TB710FU 的指定 C16 ROM。其公开源码里，`post-fs-data.sh` 原来把高通 APQ 的 `unavailable-feature` 清单放进 PackageManager 扫描路径，移除包括 `android.hardware.telephony.subscription` 在内的蜂窝功能声明。作者记录通信共享随即失效，随后撤销挂载，并将停用虚拟 RIL 的默认级别改回 0。脚本还注明该机原本就没有总开关 `android.hardware.telephony`，实际用于判定排除清单是否生效的是 `android.hardware.telephony.ims`。这把有无实体 modem 和虚拟共享所依赖的 Android 能力分开了。 [指南](https://wasddestroy.site/tb710fu-doc/generic/flash_fix_module_yu_c16.html) · [初始化脚本](https://github.com/ACLaniakea/coloros-pad-fixes/blob/v4.0.1/fix-module/module/post-fs-data.sh#L512-L535) · [服务脚本](https://github.com/ACLaniakea/coloros-pad-fixes/blob/v4.0.1/fix-module/module/service.sh#L1015-L1056)

## TB371FC C16

本地 C16 仓库 `0ab807e9fcbedff589fe9261ed204dc6103e5b9d` 实际安装通信中心、匹配 4.19 的 `oplus_vnet.ko` 和绑定到 `vircommslot1` 的按需 HIDL 服务。此前移除 `commcenterd` 的 `oneshot` 只是进程退出后重启，后续回退到用户确认能共享移动数据的 v17 行为。另有一次性逻辑仅在 `VCOMM_SHARE_NETWORK` 缺失时填入 1。对当前 C17 重跑这段逻辑没有作用，该键已经是 1。抽查 C16 候选的 vendor、odm、product、system_ext 的 permissions 与 sysconfig，查到 `android.software.telecom`，未查到 `android.hardware.telephony.*` 的 feature 声明。此范围缺 C16 system 和当时实际运行的 feature 枚举，不能把 TB710FU 的具体能力表当成 TB371FC 的已知基线。 `C16 通信记录`（历史文件） · `C16 虚拟基带 init`（历史文件）

## C17 实机与下一条验证路径

DEVICE_SERIAL，spinel，A 槽，SDK 37，APQ。只读复核确认 `r94-commcenterd` 正在运行，`IVirtualComm` 和 `ISubsysRadio` 已注册，`VCOMM_SHARE_NETWORK=1`，本地和对端 forbid flag 均为 0。PackageManager 枚举有 `android.software.telecom`，没有任何 `android.hardware.telephony.*` 声明。当前未加载旧 HIDL 服务和 ovnet。完整采样见 `device-baseline.txt`，本轮未安装模块、修改设置或刷写。

上一轮直接使用 C16 HIDL 后，46/46 符号 CRC 匹配的重编模块已能建立三个 ovnet 接口，但真实手机流量没有通过。日志同时记录了 C16 端 protobuf `IccCardStatusResponse` 必填字段错误，以及 SDK 37 端 carrier config 调用因未声明 subscription 而抛异常。两者需分开验证。下一条路径是先比对 C17 配套虚拟 provider 的卡状态消息和服务命名，再追踪 framework 如何选择虚拟 HAL、何时依赖订阅能力。TB710FU 的回退记录支持保留共享所需的框架路径，但它不能给出 SDK 37 的最小依赖集合。实机验收需要真实手机会话、平板 Wi-Fi 开启且无普通上游时的 ovnet 地址、默认网络或策略路由和实流量。 [C17 试验记录](../0017-c17-camera-connect/REPORT.md)
