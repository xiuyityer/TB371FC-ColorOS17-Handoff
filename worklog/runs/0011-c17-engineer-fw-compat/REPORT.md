# run 0011 · 工程服务查询兼容

run 0010 临时验证 OplusEngineerFwService 可以使用 checkService 走原有空服务分支。此轮把同一 JAR 修改应用到固定大小的 system_a。镜像由 run 0008 system_a 生成，仅变更 oplus-services.jar 的三个数据 extent。原始 extent、目标哈希和 DEX 反汇编见 run 0010。

实机通过原版 TWRP 校验 recovery_a 指纹与旧 system_a，写入后读取整个 system_a，哈希 76f665ffbbe2c5126993bbad1887b2532c7064b5de7eb364675de54f11b5308e。随后从 Fastboot 明确启动 A 槽。boot 仍为 run 0010 的 4.19 ring buffer + KSU，数据目录仍保留 ring map 诊断对象。

## 启动到桌面后发现的两个独立问题

- 实机 phase 1000 和用户桌面已先后到达。启动动画重播由 WifiHandlerThread 让 system_server 崩溃。旧 Wi-Fi HAL 的 WifiLinkLayerStats.radioStats 为 null，donor WifiChannelUtilization.java:239 直接取长度。新增检查跳到原有 return，保留正常统计逻辑。临时绑定修补 Wi-Fi APEX 内的 JAR 路径，签名 APEX 文件保持原样。
- 弹窗日志为 Build: Vendor interface is incompatible, error=1，系统、vendor 和 bootimage 指纹字符串相同。VINTF 兼容矩阵的具体不匹配项还待取得。未修改弹窗判断。
- Wi-Fi 补丁过了原重启时间，但显示线程随后在 libupdateprof.qti.so 等待 QSPM AIDL。改为即时查询后，原 HIDL 回退遇到 DEAD_OBJECT，未检查返回值即 abort。诊断 r2 在缺失可用 AIDL 时返回 -1 并继续原清理路径，保留可用 AIDL 调用。GPU 配置应用仍未通过，保留失败日志。
- 14:04:57、14:05:30 的实机状态均为 sys.boot_completed=1、动画停止、同一 system_server PID 12524，KSU shell su 成功。当前 Wi-Fi/QSPM 修复为临时 live bind mount，内核重启后会失效，还需整合进可冷启动产物。不要把此状态记为完整发布通过。

证据：logcat-crash.txt、logcat-after-desktop.txt、display-watchdog-25169.anr.txt、qspm-r2-state.txt；补丁哈希见 wifi-jar-patch.json 和 qspm-library-patch.json。
