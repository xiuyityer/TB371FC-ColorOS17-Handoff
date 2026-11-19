# Run 0016 · C16 模块所针对的 C17 回归

设备 DEVICE_SERIAL，TB371FC/spinel，A 槽 run 0013。最后 boot ID `REDACTED`，system_server PID 1857，开机完成，音频 HAL 运行。全程无平板重启或分区写入。恢复锁定方向 1、熄屏、原模糊和 USB 常亮设置。

## 四扬旋转已确认缺口，原生兼容候选已构建

在低音量立体声播放、输出 AUDIO_DEVICE_OUT_SPEAKER 时，旋转 90°→270°→90° 送达 AudioFlinger 和当前 32 位联想音频 HAL 的是标准 `rotation`，`TFA9894_CHAN_SELECTOR` 保持 -1，普通 Swap channel 保持 Off。实际 HAL 另有 `gsensor_rotation` 入口，`speakers_always_stereo` 会按现有通话模式与扬声器用例检查调用四扬路由。

在连续播放中直接通过 Android AudioSystem 送 `gsensor_rotation=90/270/90`，实机只读 mixer 值 3→1→3，AAudio 完成 768,000 帧、0 xrun。首次把额外参数安排在每次实际旋转后两秒的测试遇到 output standby，后两笔未进入实际四扬分派。连续播放测试保持同一用例，排除了该干扰。这里确认的是路由控制值，四个方向的听感和真实通话待测。

候选只给 `vendor.audio-hal` 配置 `LD_PRELOAD /vendor/lib/libc17_audio_rotation.so`。库仅在 HAL 查询不到 `gsensor_rotation` 时回读合法的 `rotation` 值，显式 vendor 参数优先。沿用 HAL 自己的通话、输出路由和模式检查。无常驻轮询进程，不再依赖 C16 API 19、Magisk 或直接寄存器操作。

- 基线 vendor 全分区哈希 `834d966f20117d6579e237887ebcd2690b2c513331bf0c5bcefd9f48f0865c27` 与实机一致。
- `vendor-a-audio.img` 899,739,648 字节，SHA-256 `f9ca92fac0ba74e389e71aab06a280a7b65d8c6c654ed1c40c6390ff6b442310`。
- ext4 检查、修改文件回读和 SELinux 标签一致。实机独立命名空间只读挂载，真实 vendor service 路径的 linker --list 解析到候选库。随后将隔离测试程序临时绑定到同一路径，使用实际 `/apex/com.android.vndk.v30/lib/libcutils.so`，11 项均通过。第一版从 `RTLD_NEXT` 查找未跨到 VNDK，已改为精确库句柄。初稿证据保留，初稿镜像已删除。
- 最终候选未刷写，仍需实机冷启动确认 init 服务的预加载和运行时监听。可以先单独在现有 C17 基线上验证 vendor，再按 run 0015 清单测试配套系统镜像。

## 锁屏控制中心卡顿已复现，未确认调度故障

固定 ADB 下拉/收起流程，前两组有足量帧的样本分别为 104/439、27/145 卡顿帧。atrace 中最长 RenderThread 帧为 48.30 ms，其中运行 CPU 47.39 ms，可运行等待 0.91 ms。该帧包含约 36 ms 的 shader_compile 路径，另一长帧的 syncFrameState 含纹理上传。当前证据集中在绘制路径，不能归因于旧 schedtune 模块缺失。

尝试使用原生全局模糊开关做 A/B/A。确保屏幕亮起后，开启/关闭/恢复的卡顿占比分别为 8.71%、11.88%、9.81%，P95 25/26/25 ms。没有稳定改善，已还原。不改线程绑核、cgroup 或用户视觉设置。该测量覆盖锁屏控制中心，应用切换和桌面手势仍未验。

## AI 与 B 站

- 旧 AI 包名单仍为六个已停用、一项缺失，对应进程未发现。当前实机没有这组包仍在运行的证据，没有做额外禁用。run 0015 的原生可选控制保留。
- 实机原生 B 站规则缺少可拖动标志和旧直播例外，run 0015 已补入工厂 XML。当前未安装 B 站，界面回归和云规则是否覆盖仍待确认。
