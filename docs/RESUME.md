# 从清刷版接手

## 恢复工作镜像

需要 Python 3.9 及约 10 GiB 输出空间。输入是维护者保留的文件 TB371FC-C17-KSU-Clean-20261118.zip，外部 SHA-256 见 [release.sha256](../baseline/release.sha256)。

```sh
python3 tools/extract-baseline.py /path/to/TB371FC-C17-KSU-Clean-20261118.zip ./images
```

脚本先校验 ZIP，再把有分区内容的 Android sparse spans 还原为 13 个逻辑分区镜像，并分别核对大小和 SHA-256。也会抽出独立 boot_a、recovery_a、super 元数据和原包中两份应用。仅处理例如刷新率时，加 `--only my_product_a.img` 可减少输出。所有输出均来自持有者提供的包。[完整分区清单](../baseline/manifest.json)

## 构建和验证下一轮

1. 冻结提取出的基线和目标分区。保留 A 槽、原版 TWRP、分区容量、AVB 现状及联想的底包固件。完整清刷包的 B 槽动态分区为空。
2. 按 [修复索引](FIXES.md) 选择目标。原历史脚本保留所在运行路径和依赖名称，便于读清改了哪个文件、对应的输入哈希、压缩区段和厂商二进制补丁位置。脚本中的 DEVICE_SERIAL 和工作目录为占位，早期中间镜像已清理。新修复应直接从刚提取的当前分区开始。不要在成品上重叠应用已经集成的历史补丁。
3. macOS 上用区分大小写的 APFS 或 Linux 文件系统解包。EROFS 用 1.8.10 的 dump/fsck/mkfs 验证，ext4 vendor 使用 e2fsprogs 1.47.3 的 debugfs、e2fsck。保留 uid、gid、模式、SELinux 标签、扩展属性、分区大小以及映像尾部结构。替换小文件可参照 [条件严格的 pcluster 修补工具](../tools/historical/patch_erofs_compressed_pcluster.py)。
4. 比对旧、新整镜像 SHA-256，记录目标槽位和对应 TWRP 读回。先用实机测试受影响的分区组合，再决定是否生成新的全量清刷包。单独刷入经过核对的镜像可参考 [历史 TWRP 流程](../worklog/runs/0017-c17-camera-connect/flash-camera-set.sh)。该脚本需先适配设备序列号、绝对路径和旧新哈希。
5. 打完整包时，以清刷版的 super 布局和保留的 13 个分区为输入。可参考 [稀疏分片与读回](../worklog/runs/0022-c17-line-flash/build-package.py) 的编码流程。重新校验全展开 super、每个分片、分区与 APK，更新 manifest.json、payload.sha256、flash-plan.tsv。保留同一 ZIP 中的 Windows 和 Mac 一键确认入口。原版 TWRP 作为独立 recovery_a，刷写前确认用户数据将清空。

清刷 ZIP 是恢复当前基准的入口。原始完整 C17 donor、原版 TWRP 文件和匹配的 TFA 固件由持有者独立取得。仅凭历史报告从厂商源镜像重做全部集成需要逐阶段重放，已有基准可省去这些步骤。
