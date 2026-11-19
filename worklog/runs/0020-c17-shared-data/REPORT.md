# Run 0020 · C17 通信共享实机验收

设备 DEVICE_SERIAL、TB371FC/spinel、4.19.325-perf+ #2、C17 SDK 37、KernelSU，A 槽。以上一轮 stable-sharing vendor 为起点。

## 修复

PhoneSwitcher 实际选中虚拟数据订阅 1，但 max data attach 数是 0，phone 0 因此 inactive。AOSP PhoneCapability 回退本来为 1，Oplus 的高通 OEM Hook 遇到 RADIO_NOT_AVAILABLE 时又将其覆盖成 0。预算 JAR 的单字节补丁仅将异常或空结果分支改为 1，保留成功查询。临时绑定验证 phone 0 变成 active。断开普通 Wi-Fi 后，上网请求进入 DataNetworkController，随后遇到登记状态 NOT_IN_SERVICE。

供体虚拟 AIDL 的 DATA_REGISTRATION_STATE 返回 REQUEST_NOT_SUPPORTED。Oplus framework 另有从 DMTP 缓存读取真手机登记的路径，当前 ro.carrier=unknown 未命中它。临时设为 wifi-only 验证了实际手机 PS 和 CS 登记可到 HOME，同时发现远端 slot 1 使本地长度为 1 的状态与信号缓存越界。最终恢复全局 ro.carrier=unknown，只在本机哈希匹配的 OplusVirtualComm 修改原 Wi-Fi 虚拟状态路径。缓存按两个 remote slot 分配，三处上界改为严格小于。继续使用手机发来的 DMTP 状态。同一 boot 连续发生电话进程崩溃后，CellularDataService 绑定返回 false，正常冷启动后重新绑定成功。

## 刷写和验收

A 槽 vendor SHA-256 60e4060dac130e5d956fb22c5c88e0a47cbbfaa7fc4b67ef40fee1b6bbf4e56f，e2fsck、三个修改文件的内容/权限/标签以及原版 TWRP 整块回读均通过。boot ID REDACTED。冷启从 vendor 绑定两个新增修复，保留上一轮无基带误判修复。物理蜂窝硬件和固件没有改动。

用户确认一加 11 通信共享功能正常。21:03:12 实机 SETUP_DATA_CALL 响应成功，ovnet0 获得地址、DNS，电话框架报告 CONNECTED，网络 101 状态 VALID。随后采样 ovnet0 TX 15,583、RX 22,386。采样时普通 Wi-Fi 已恢复为默认网络，ovnet0 已退出。较晚拨号曾返回 0x1103，未单独验收反复切换恢复。冷启动到用户确认后，电话进程持续为 4666，crash buffer 为空。投屏、拨出/来电、短信与移动网络设置 UI 本轮未重新验收。

证据在 cold-data-state.txt、user-pass-data-radio.txt、user-pass-data-state.txt、user-pass-data-crash.txt 与 twrp-console.txt。
