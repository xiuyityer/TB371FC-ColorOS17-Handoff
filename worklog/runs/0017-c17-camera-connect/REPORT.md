# Run 0017 · C17 跨端互联、相机和模块收尾

设备 DEVICE_SERIAL，Lenovo TB371FC / spinel。实机使用 C17 A 槽、4.19.325-perf+ #2、KernelSU 与原版 TWRP。本轮使用 TWRP 写动态分区并逐块计算 SHA-256，fastboot 确认 A 槽后继续启动。测试过程未格式化 userdata。

## 相机

原生 Oplus 相机首先缺少配置在产品覆盖路径中的 SDK shared libraries。把对应注册 XML 放进 PackageManager 实际扫描的目录后，冷启动确认几个可选库能解析，原有 NoClassDefFoundError 消失。相机随后在模式与相机 ID 查找（`jb.c1.f` → `ra.k.a`）中因 FeatureConfigureAdapter 为空崩溃，继续适配需要还原供体产品配置与硬件映射。

采用 C16 同签名 ZUI 相机。APK SHA-256 为 `0c72c201cef16bb4e187257690d7963b3c49c13dfa990ebb3cc1b53da57e7b7e`。用户确认安装和功能正常，已执行 `pm disable-user --user 0 com.oplus.camera`。ZUI APK 安装在 userdata，适用于这台平板当前用户。解锁后 `STILL_IMAGE_CAMERA` 解析到 `com.zui.camera/.CameraActivity`。通用应用内调用的 `IMAGE_CAPTURE` 和 `VIDEO_CAPTURE` 未验收。整包预置尝试超出 my_product 分区 41,086,976 字节，未刷入。

## 投屏

C16 的 ODMF 补丁与 C17 供体存在相同问题：`AndroidVideoDecoder.initDecodeInternal` 用 sharedContext 判断是否设置解码像素格式，导致已有 Surface 被忽略。参照 C16，仅把该字段引用换成实际 Surface。用户实测临时加载后手机投屏能显示内容。系统集成由 init 在 OPEX 就绪后、Zygote 前绑定只读 ODMF JAR，保留已签名 OPEX 原件。冷启动从 PID 1 挂载表确认源是系统镜像，目标 SHA 为 `ab4937e230a36e21e33fb848bdd075e63633175e1049eb24e5fd2842eec983f5`。用户在移除旧虚拟基带后的 system_ext 镜像冷启上再次确认投屏有画面。

## 网络共享

复核 C16 文档与运行物料。尝试过 C16 HIDL 虚拟基带配合重新构建的 ovnet。C16 原模块与当前 #2 内核有 21/46 CRC 不匹配。重编模块 46/46 匹配，实机建立 ovnet0 至 ovnet2。HIDL 实例也曾正常注册。用户实测仍无网络。日志显示跨端通信已建立，虚拟 SIM 仍是 CARDSTATE_ABSENT、`checkSimStatus [false]`，没有共享接口或路由接管流量，旧 RIL 报 protobuf IccCardStatusResponse 必填字段缺失。

冷启动自动注册旧虚拟基带还会触发 SDK 37 的 `updateConfigForPhoneId is unsupported without android.hardware.telephony.subscription`，导致 `com.android.phone` 反复崩溃。临时停止后恢复。供功能测试的 system_ext 镜像仅集成投屏补丁，移除实验性旧基带和 ovnet 自动加载。下一轮应从 C17 供体 AIDL 虚拟基带和 protobuf 21.12 这一组出发，比对 C17 framework 的实际服务选择与订阅能力门槛。供体组件与 ELF 依赖已保存在本目录。验收时应断开平板普通 Wi-Fi 上游，同时看到虚拟接口及路由建立并确认平板能通过手机访问网络。

## 原生功能与模块

五个旧模块都退出了 KernelSU 活动目录，备份在设备 `/data/adb/c17-retired-modules/run0017`。原生笔刷新率服务随 init 启动，AI 模块关停前的恢复状态迁移到 `/data/misc/c17-ai-controls/state.txt`。B 站双窗规则留在 my_product。前台调度与隐私密码实验模块一并归档，无原生等效功能。修正音频 HAL 实际由 `/vendor/etc/init/hw/init.qcom.rc` 覆盖的问题后，实机确认 HAL 映射 `/vendor/lib/libc17_audio_rotation.so`。此前原生刷新率、B 站规则或扬声器行为的验证范围见 run 0015 和 0016。

## 产物与日志

首批写入见 `partitions.tsv`；含旧虚拟基带的第二批为诊断镜像，见 `connect-partitions.tsv`。供后续使用的镜像以 `mirror-partitions.tsv` 为准，与 run 0014 system、run 0015 my_product、当前 vendor 音频覆盖版组合。网络和电话进程证据见 `retested-radio.txt`、`donor-network-dependencies.txt`、`cold-connect-crash.txt`。

用户复测投屏的 system_ext 镜像 928,116,736 字节，SHA-256 `33d42b4e7816dae913eb0c2af5f299999d813601b6b931bbae9e922d67ee5c7e`。离线校验 3,968 个 inode、3,522 个文件，权限、所有者、xattr 和内容通过。TWRP 整块回读一致。实机 boot ID `REDACTED`，`sys.boot_completed=1`，开机动画停止，早期 crash buffer 为空。首次执行刷写脚本时未通过 shell 调用，脚本因缺少执行位未运行；随后用 `sh` 调用同一脚本完成。详见 `twrp-mirror-console.txt`、`fastboot-mirror-console.txt` 和 `cold-mirror-state.txt`。

当前框架 `OplusRilImpl.setVirtualRadio` 静态证据显示直接调用 HIDL V1.5，而供体 ODM 的虚拟基带导出 AIDL radio 接口，库内实例前缀为 `/vircomm`。下一轮可核对供体启用路径和实际服务实例，再确定需要适配的接口。见 `c17-ril-interface-selection.txt`。

空间清理删除了超区 ZUI 预置实验镜像以及两份保留有补零版的中间镜像，逻辑大小合计 4,454,248,448 字节。APFS 实际可用空间增长与逻辑大小不同。

## “请先移除本机 SIM 卡”提示与当前设备

用户在投屏通过的同次冷启报告，通信共享详情页提示移除本机 SIM。平板是 Wi-Fi SKU，系统未声明 telephony feature，`gsm.sim.state` 未上报，旧 HIDL 虚拟基带已从 system_ext 移除。供体产品属性仍有 `ro.vendor.oplus.radio.multisim.config=dsds`、`ro.radio.noril=no`、`ro.vendor.radio.noril=no`，实际作用待逐项比对 C16。

提示资源在 WirelessSettings 的 `remove_phone_sim_card_for_communication_sharing`。代码把该提示用于界面状态 2。追踪事件管理器，状态 2 的更新路径之一来自 `VirtualCommServiceState.getPeerDeviceName()` 和设备连接状态的转换，界面此处没有直接读取物理 SIM。设置中的本地和对端禁止标志在最后采样均为 0。需要把真实失败复现和虚拟共享的对端状态同一时间采集，当前日志不足以断言这条提示是哪个状态变化触发。另有独立的物理 SIM 查询在 Contacts 进程回报 null，没有证据表明存在实体卡。

为验证已知的开机 ANR，又实机测试了非阻塞 HIDL 查询候选。当前运行的是 `radio-lookup-partitions.tsv` 对应镜像，哈希 `ae8ae03421fa64048f0cdcec937599353e0ed5eb2496257a8ad31b197ee412e3`，boot ID `REDACTED`。整块 TWRP 回读和系统启动通过，投屏 JAR 哈希与用户已验收版本一致。实机仍显示 HIDL 等待和一次电话进程启动 ANR，单改 retry 参数无效。另记录一次 `com.oplus.subsys` 启动服务 ANR，尚未确定关联。9 分钟后的 crash buffer 为空，system_server 稳定，全程未恢复旧虚拟基带。以 `mirror-partitions.tsv` 对应版本作为用户已实测投屏的基线，当前机载尝试与该基线的差异见 `system-ext-radio-lookup-plan.json`。
