# SC6103 Distributed Flight Information System

Java 17 服务端 + Python 3.10+ 客户端，IPv4 UDP，手工二进制协议 v1.0。

**2026-10-10：A 通信层已完成，与现有 B/C 模块完成真实本机 UDP 集成。Java 17 运行时下 200 项自动化测试及 16 项网络实验全部通过。三台物理电脑演示尚未执行。**

| 分工 | 成员 | 内容 |
|---|---|---|
| A | Zhang Zhiyin | 二进制编解码、UDP、分派、ALO/AMO、丢回复、日志与集成验证 |
| B | Peng Jinyu | 固定数据、六项业务、订阅监控、原实验工具与业务测试 |
| C | Ji Chengyu | Python 客户端、重传、回调过滤、菜单与客户端测试 |

## 启动

在仓库根目录运行。需要 JDK 17+（包含 javac）与 Python 3.10+，程序无第三方依赖。

```sh
python3 -c 'from experiments.run_suite import compile_java; compile_java()'
java -cp server/build/classes flight.ServerMain --bind 0.0.0.0 --port 6789 --semantics amo
```

另一终端：

```sh
python3 -m client --server 127.0.0.1 --port 6789 --semantics amo
```

Windows 将 `python3` 换为 `python`，也可用 `server/build.ps1`；macOS/Linux 可用 `sh server/build.sh`。跨电脑将客户端地址换为服务端实际 IPv4。`--check` 仅检查配置，不代表网络验证。

## 复现与证据

```sh
python3 -m experiments.verify_all --matrix
```

每次使用独立输出目录、新进程、新 session 和种子数据；完整命令、客户端/服务端/代理日志与执行次数审计均保留。只运行 16 项实验可用 `python3 -m experiments.run_suite`。

- [最终验证证据](evidence/a/README.md)：200 项测试、16 项实验，真实 Java 17 运行环境。
- [实验结果](evidence/a/release-java17/matrix/results.csv)：实际状态、执行次数与缓存命中。
- [A 交接](server/A_HANDOFF.md)、[服务端](server/README.md)、[客户端](client/README.md)。
- [英文 PDF](output/pdf/SC6103_Project_Report.pdf)、[完整英文报告](report/项目报告.md)、[A 章节](report/A_通信与调用语义.md)。
- [权威协议 v1.0](SC6103_接口与数据类型规范.md)、[固定数据](experiments/seed_manifest.md)。
- [三机演示](experiments/demo_steps.md)、[提交检查](SUBMISSION_CHECKLIST.md)。

旧指南/审查保留历史记录，其“待 A 实现”等状态以 2026-10-10 更新及最终证据为准。线上字段、操作编号和公共 DTO 未变更；ProtocolException 仅增加本地错误回复元数据。贡献比例由全组核对后填写，不按计划工作点推算。

生成源码审核 ZIP：`python3 tools/package_submission.py`，默认写入仓库外的 `../output/SC6103_Group_Project_Review.zip`。源码包不依赖 Git，含报告、原始证据与文件 SHA256 清单。
