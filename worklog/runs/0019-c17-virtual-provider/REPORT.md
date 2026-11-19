# Run 0019 · C17 AIDL 虚拟基带

设备 DEVICE_SERIAL、TB371FC/spinel、C17 SDK 37、4.19.325-perf+ #2、KernelSU，A 槽。沿用原版 TWRP 做分区回读。基准是 run 0017 的 system_ext 和音频兼容 vendor。

## 确定的接口与缺口

C17 供体的 ODM 中包含 `virtual_daemon.rc`，两条服务分别用 `subsys_daemon -l lib-virtual-modem-radio-aidl.so -i 0/1`。供体 `telephony_manifest_dsds.xml` 声明六种 AIDL radio V2 接口，每种都有 `vircomm1/2`。本机 donor C17 framework 的 `OplusRilImpl.setVirtualServiceProxy` 通过这些名称选择 AIDL，`OplusHalWorkerPrimary.canSwitchToVirtualModem` 同时要求两个 IRadioData 实例已声明。旧适配的 vendor manifest 只有旧 HIDL vircommslot1 及旧 HIDL IMS。实际声明与应用期待不符。

候选仅提取供体虚拟 daemon、通信中心、其局部依赖和六类虚拟 AIDL 声明；Wi‑Fi 机型不运行供体 QMI/实体 modem 服务。ovnet 使用 run 0017 已核对 46/46 CRC 的 4.19 模块。音频 HAL 原替换仍在。代码与供体依赖见 `build-vendor-provider.py`、`virtual-provider.rc`、`provider-dependencies.txt`、`aidl-selection-dex.txt`。

## ABI 试验

生成 vendor 前，私有 mount namespace 下的 VINTF 检查为 `compatibility_status=0`，枚举 12 个实例。首次构建文件模式设置少一位八进制 0，被 e2fsck 拦下。脚本增加常规文件类型断言并重建，错误镜像未写入。

首次实际冷启的 vendor SHA-256 是 `51549d545ce8ea99c29042f1066aaa553daed8ff06a973173bf1711af7246a03`，TWRP 回读一致。系统启动完成，ovnet0-2 出现。空闲链路未有流量。三个通信进程因缺新 libc++ 符号持续退出。此前 `linker64 --list` 只证明依赖路径能找到，未覆盖实际重定位。

在同一 boot 中用厂商原始 libc++ 临时加入服务私有库路径，通信中心与 12 个 AIDL 实例实测全部注册。随后 `com.android.phone` 连续因 `updateConfigForPhoneId is unsupported without android.hardware.telephony.subscription` 崩溃。此时已临时停止两路虚拟基带。这个错误在 C16 HIDL 与 C17 AIDL 两次试验均复现。供体 AIDL 路线消除了接口版本差异，订阅能力是独立故障。

## 本轮用户复测与两处 IMS 崩溃

第二版 vendor 加入进程私有 libc++ 和 `telephony.subscription`，SHA-256 `2c06009fdab601df2696d25d8601201b2a6ae5b2b87cc12975835c8e190da13a`。冷启三进程上线，12 个 AIDL 实例注册，原 carrier config 异常未复现。用户报告界面能认出一加 11，重试后立即断开，仍无法访问网页，移动网络页白屏或闪退。 `android.settings.NETWORK_OPERATOR_SETTINGS` 解析为 `com.android.phone/.simsettings.OplusSimSettingsImpl`，此时同一宿主进程持续异常重启。系统休眠时 ADB 未能实际呈现该页面，尚无 UI 通过证据。

收集用户时段的崩溃与无线日志后，确认两条独立堆栈。两路 native `subsys_daemon` 处理 DSDA 通知时，`ImsCallManager::onDsdaModeChanged` 对未注册的 Handler 增加强引用，引发 SIGSEGV。Java `OplusImsCapabilityManager.updateVoNrSwitchFromPhone` 假设非空 Phone 一定有 ImsPhone，在收到手机 VoNR 状态时引发 NPE。补入供体私有 QTI IMS 插件，两路 native 进程均映射插件且 PID 稳定；Java 崩溃仍在。随后对 DEX 的该调用点加空检查。临时绑定前验证原 APK 哈希，绑定后确认新 `com.android.phone` 进程的 maps 和哈希。手机真实会话反复重连时，phone PID 13066 保持稳定，收到手机转发的虚拟卡 PRESENT 状态，未再出现两种崩溃。ovnet 仍 DOWN，未观察到 HAL setupDataCall。

第三版把两处修复持久集成到 vendor，并为虚拟数据试验增加 `android.hardware.telephony.data`。供体 IMS 插件改走服务的私有库路径。开机先由 PackageManager 扫描原签名 APK，boot_completed 后仅在精确哈希匹配时挂载运行时保护并启动虚拟 HAL。原始签名 APK 仍保留在 system_ext。未声明其他蜂窝 capability、未增加物理 modem 服务。

## 控制中心闪烁、虚拟卡误判与数据路由

用户在第三版反馈移动数据图标反复显示一加 11 的中国电信卡再变灰。实机 `com.android.phone` PID 4607 与两个虚拟服务均稳定，crash buffer 为空。20:13:33.858 虚拟订阅进入 READY，20:13:33.873 的应用日志因 `mCardRemoved` 更新且 `mIsWorkingOnVirtualModem=false` 产生本机禁止位 256，`updateTransportAvailableP:false;120`，20:13:33.876 共享会话断开，20:13:33.959 虚拟订阅变为 ABSENT。数个周期相同。DEX 确认禁止位 256 位于 `DistributedCommDev.getChannelForbidFlag()` 的无基带分支，`mCardRemoved` 来自该设备 TelephonyManager 的 SIM 状态。

只在无基带分支去掉错误的本机实体卡禁止位，保留对端、同账号、用户授权和其余禁止位。在同一 boot 临时绑定后，由 `com.oplus.subsys` 加载新 APK。共享订阅达到 LOADED，运营商号 46011，默认数据订阅 ID 1，本机禁止位 0，系统加载四个运营商数据配置。对平板暂时限制 Wi-Fi 自动连接期间保留 Wi-Fi 开关，实际确认 wlan0 无普通路由，三个 ovnet 仍 DOWN。测试退出后撤销限制、普通 Wi-Fi 重连。无线日志明确看到默认 INTERNET 请求进入 TelephonyNetworkProvider，却报 `onNetworkNeeded: Not applied`，未下发 SETUP_DATA_CALL，故端到端网络尚未通过。后续应查 PhoneSwitcher 为什么不给现有虚拟订阅分配默认请求，并比对缺失的 RadioConfig HAL 路径。RadioConfig 的缺失与目前现象同时存在，因果尚未验证。

将该无基带误判修复集成到 stable-sharing vendor 候选。与前版一样在 boot_completed 后先检查原签名 APK，再只读绑定两个恢复版本，重新启动各自进程后拉起虚拟 HAL。具体来源、开机日志与联网试验见本目录下的 `flicker-sharing.txt`、`no-physical-card-radio.txt`、`data-only-radio.txt` 和 `vendor-stable-sharing-partitions.tsv`。

最终 A 槽 vendor SHA-256 为 `a9606e70633dcdf4e2f0076a5cc2fa5e494f6297c0e6822a1f3b71d061522c10`，38 个加入或替换的文件经过内容与权限标签回读，TWRP 整块回读一致。boot ID `REDACTED`，两处绑定均指向 vendor 分区而非 userdata。约 102 秒后 `com.android.phone`、`com.oplus.subsys` 与两路虚拟基带均运行，期间 crash 及 ANR 缓冲为空，KernelSU 与旧投屏补丁哈希复核通过。设备仍锁屏，持久版尚无手机联测或移动网络页面目视确认。临时版的误判修复有真实手机卡状态稳定的证据，实流量未过。见 `cold-stable-state.txt`、`cold-stable-followup.txt` 和 `twrp-stable-sharing-console.txt`。
