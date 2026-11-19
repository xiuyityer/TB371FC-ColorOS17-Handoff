# Run 0014 · C17 远程排查与镜像集成

设备 DEVICE_SERIAL，TB371FC/spinel，A 槽。用户离开平板，本轮只通过 ADB 使用已启动的 run 0013。没有重启平板或写入分区。15:06:26 仍为 boot ID `REDACTED`，system_server PID 1857，`sys.boot_completed=1`，动画停止。run 0013 的 VINTF 整体检查与 manifest 检查仍返回 0，KernelSU shell 提权可用。

## GPU 预缓存

run 0013 的三次 SIGSEGV 指向 PreCacheService 的锁访问。当 GPU 服务已经注册但异步初始化仍未保存 this+0x68 的 PreCacheService 指针时，Oplus Binder 分派会把空对象传给处理函数。补丁在六个 PreCache 调用的分派口增加空值检查，返回 `-ENODEV`，保留已就绪处理分支、原来栈帧和其他事务。平板上的隔离测试确认六个分支返回 -19，七个未就绪场景下的其他事务返回原有的 0。

使用 init 的挂载命名空间临时绑定该库，只重启名为 `gpu` 的服务。首次脚本用挂载源名检查进程 maps，内核显示的是目标名，触发了回退动作，但普通 umount 因挂载正在使用而返回 EBUSY。随后在 GPU 进程命名空间核对实际映射的 inode 41582 和库哈希，新 PID 11020 确认使用了补丁。已修正后续脚本的检查和回退方式。system_server PID 始终是 1857，至 15:06:26 crash buffer 没有新增记录。GPU 临时覆盖仍生效，重启后恢复 run 0013 启动内容。独立测试覆盖未初始化分支，当前启动周期未重新发生自然触发的冷启竞争。

## 电话进程 ANR 与硬件检查

`com.android.phone` 的 LOCKED_BOOT_COMPLETED 广播超时，ANR 主线程栈为 `OplusRilImpl.setVirtualRadio → IRadio.getService`，反复等待未注册的 `android.hardware.radio@1.5::IRadio/vircommslot1`。制作了独立 JAR，把该查询的 retry 参数改为 false，沿用现有的 NoSuchElementException/RemoteException 回退。平板 ART dexdump 确认目标方法只改一条指令。该补丁未加载进电话进程，也未加入下面的镜像，仍需一次单独实机测试。

Wi-Fi 主动扫描发现 21 个热点，其中 2.4 GHz 12 个、5 GHz 9 个。设备处于 RUNNING_LOCKED，Wi-Fi 当前未连接，扫描结果只证明扫描链路可用。系统枚举两颗摄像头、41 个传感器以及 NVT 触屏和手写笔设备。Bluetooth 处于 ON。未验证 Wi-Fi 联网、蓝牙配对、相机成像或触控输入。SELinux 仍是 Permissive，avc-top.txt 汇总了当前拒绝记录。

## 可成对测试的离线镜像

- `system-a-integrated.img` 954,871,808 字节，SHA-256 `5d2e0984ab35386d1818a178259b22cdd2feb5d2628c78551153a0431fed4774`。
- `system-ext-a-integrated-slot.img` 928,116,736 字节，SHA-256 `ac39a36ca0c17ad290f59ff9d90a35b4c7f021483c2707d4f47e08aa24931827`。128 KiB LZ4HC pcluster，实际文件系统 920,084,480 字节，余量填零。首次 64 KiB 输出超出 761,856 字节，已删初稿镜像并保留构建记录。

镜像成对使用。system_ext 直接集成 GPU 与 QSPM 库，并提供 Wi-Fi JAR、BPF 对象、netd 兼容库。system 从 system_ext 读取这些文件。Wi-Fi 仍通过 init 文件挂载，signed Wi-Fi APEX 保持原样。netd 仍借助 LD_PRELOAD，路径已移出 userdata。

system 通过 fsck，system_ext 全量回读一共 3,961 inode、3,515 文件，权限、所有者、xattr 及内容通过。两张镜像均由本机 4.19 内核在独立命名空间内只读 loop 挂载，完整镜像及指定文件哈希一致。netd 的 linker64 --list 解析到了候选的 `/system_ext/lib64/c17-netd.so`。首次只读测试清理时遇到 toybox 自动分离 loop 的差异，最终脚本退出成功，确认无残留 loop 后删除平板上的两份临时镜像。镜像尚未写入分区，冷启动未测。原版 TWRP 和当前 run 0013 启动保留。
