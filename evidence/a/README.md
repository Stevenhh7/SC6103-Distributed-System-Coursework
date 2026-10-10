# A 验证证据索引

最终验收使用 **release-java17/**（2026-10-10，从源码 ZIP 解压的无 Git、无编译缓存目录运行）；summary.json 全部 exit_code=0。

| 范围 | 数量 | 原始输出 |
|---|---:|---|
| A 协议 | 19 | release-java17/a-protocol.txt |
| A 语义/传输 | 21 | release-java17/a-semantics.txt |
| B 业务与监控 | 34+15 | release-java17/b-business.txt、b-monitor.txt |
| C 客户端 | 63 | release-java17/c-client.txt |
| 实验工具 | 36 | release-java17/experiment-tools.txt |
| 真实 Java/Python 网络集成 | 12 | release-java17/java-integration.txt、network/ |
| 真实 UDP 故障实验 | 16 | release-java17/matrix/results.csv |

共 200 组自动化测试，另 16 项实验。不是 216 台机器或 216 次独立统计采样。所有 UDP 测试在同一物理电脑的独立进程/socket 上进行，三机验收尚未执行。

环境：macOS ARM64，Python 3.13.1；javac 21.0.5 使用 --release 17，实际 Java 运行时 Temurin 17.0.20.1。精确信息在 environment.json；源码 SHA256 在 source-manifest.json。release 验证的 baseline 为 null，表示源码包不含 .git；源码哈希用于对应提交中的实际文件。早期 final-java17 目录的 baseline 是当时的基准提交，不能代替源码哈希。

每个 matrix 子目录含 client/server/proxy 原始日志、命令、分析和服务器执行审计；以身份/字节关联真实 BUSINESS_EXECUTED、HISTORY_SAVED、CACHE_HIT 和 DROP_REPLY。network/ 保留边界集成服务端日志。

此前 final-java17 为仓库内 Java 17 验证，随后仅调整验证工具以支持无 Git 的源码包；release-java17 是清洁源码包复验。其余目录为开发阶段记录：udp-matrix-01 和 boundaries-* 在 Java 21 上运行；first-baseline 在准备阶段遇到路径处理异常，未完成业务实验，不算通过。最终 Java 17 结果取代它们用于本次验收，但原始证据保留。

复现：仓库根目录 `python3 -m experiments.verify_all --matrix`，自动生成新目录，不覆盖本次证据。

release 进程命令和 matrix/results.csv 的原始 evidence 路径相对于当时解压的临时源码根目录记录，原样保留。仓库内可直接导航的统一路径见根 experiments/results.csv；无需存在原临时目录即可按 README 重跑。
