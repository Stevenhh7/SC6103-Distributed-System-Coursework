# SC6103 Distributed Flight Information System

Java 17 服务端 + Python 3.10+ 客户端，IPv4 UDP，手工二进制协议 v1.0。

**2026-10-13：最终英文报告已整理完成，包含23页、18张精选截图和11组图示。2026-10-12已完成三台电脑的实验预演，覆盖业务操作、连续回调、双客户端监控、航班隔离及六组ALO/AMO丢回复对比。原有本机验证记录为200项测试和16项UDP实验通过；课堂演示安排在10月17日。**

## 最终报告与实验材料

- [最终英文报告 PDF](output/pdf/SC6103_Project_Report.pdf)
- [完整源码 ZIP（NTULearn 源码入口）](output/source/SC6103_Source_Code_20261013.zip)：包含全部 Java/Python 源码、构建说明、测试和原始证据；与下方报告素材包分开。
- [可编辑报告 Markdown](report/项目报告.md)
- [报告与证据下载包](output/report/SC6103_Report_Editable_Package.zip)：包含报告、图片、原始截图、B的三轮日志及报告生成工具。
- [原始截图与证据索引](evidence/demo/20261012-submitted-screenshots/README.md)：保留全部28张原始截图及SHA-256清单。

实际贡献比例：三人平均分配，Zhang Zhiyin（A）、Peng Jinyu（B）、Ji Chengyu（C）各33.33%；精确比例均为三分之一，显示总和99.99%为舍入所致。已补入A端原始服务器日志及94项证据核对，包含航班隔离的正确接收端验证。演示：10月17日LT8，slot 11，14:15-14:30，建议14:00到场。下载包为报告材料包，完整程序源码仍在本仓库。

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

旧指南/审查保留历史记录，其“待 A 实现”等状态以实际实现及最终证据为准。线上字段、操作编号和公共 DTO 未变更；ProtocolException 仅增加本地错误回复元数据。最终报告已填入等分贡献比例、演示编号和时间。个人互评表须由每人单独提交，GitHub上传不等于NTULearn提交。

生成源码审核 ZIP：`python3 tools/package_submission.py`，默认写入仓库外的 `../output/SC6103_Group_Project_Review.zip`。源码包不依赖 Git，含报告、原始证据与文件 SHA256 清单。

本次完整需求审核见 [2026-10-13最终审核与提交指南](FINAL_AUDIT_20261013.md)。
