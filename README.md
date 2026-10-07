# SC6103-Distributed-System-Coursework

Java17目标服务端 + Python3.10+客户端，IPv4 UDP航班信息系统。

更新时间：2026-10-07。**B的固定数据、六项业务与监控已实现并通过49项独立Java测试；C客户端与独立测试已交付。A的codec、UDP、分派/历史/调用语义仍为占位，因此整套服务尚未进行真实网络联调。** 编译、模拟测试或预期结果不能代表网络通过。

## 目录与职责

| 目录 | 负责人 | 内容 |
|---|---|---|
| [client](client/README.md) | C | Python codec、Invoker、monitor、菜单与实验驱动；自身测试/章节 |
| [server](server/README.md) | A/B | A协议/通信/语义；B数据/六业务/监控；[服务端待办](server/TODO.md) |
| [experiments](experiments/cases.md) | B | 种子、复位、用例/结果、全丢代理、runner与三机演示步骤 |
| [report](report/项目报告.md) | 各自写，B汇总 | B章节已完成、C已交付，A章节与真实联调待补 |

现行目录为client/、server/，旧指南client-python/server-java草案不再使用。线上接口仍严格依据v1.0。

## 独立验证与配置检查

从仓库根目录的PowerShell运行，不下载外部库：

```powershell
python -m client --help
python -m client --check
.\server\build.ps1
.\server\test-b.ps1 -EvidenceFile evidence/b/2026-10-07-b-self-tests.txt
python -m unittest experiments.test_analyze_results experiments.test_runtime_check experiments.test_udp_loss_proxy -v
java -cp server/build/classes flight.ServerMain --help
java -cp server/build/classes flight.ServerMain --check
```

编译使用javac --release17；本次实际JDK25.0.4，JDK17运行环境需最终复核。--check只验证配置/装配，不开socket。Java普通启动当前仍提示A-03未实现；Python菜单与实验已实现，真实Java连接需要A通信层。

B测试直接调用业务方法，不依赖UDP/C；代理的真实本机UDP自测仅证明故障工具行为。完整接口交接与测试见[B_HANDOFF](server/B_HANDOFF.md)。server/README.md仍有A最初框架说明，B当前状态以这里和交接记录为准。

规划检查，不创建进程、socket或结果记录：

```powershell
.\experiments\run_suite.ps1 -Case all_reply_loss -Semantics amo -DryRun
```

A完成后去掉-DryRun，按[cases.md](experiments/cases.md)逐例执行。runner检查端口和就绪，按请求身份/阶段/状态/attempts与全丢证据验收，保留analysis.json和每例result.csv；真实执行/cacheHit需A日志复核。三人后续安排见[B复查与联调计划](experiments/B_复查与队友联调计划.md)，三机步骤见[demo_steps.md](experiments/demo_steps.md)。

VS Code打开整个仓库；.vscode/settings.json将server/src设为Java源码根目录，包flight。配置说明见原server/README.md。

## 协作约定与文档

- 每人维护自己模块的测试和报告；B组织实验、集成安排与报告汇总；C保留客户端实验调用驱动。
- A/B共享同一监控对象；B不操作socket，A不直接修改业务容器。
- A/C共用一个二进制规范，不另建DTO，不单方改字段。
- 实验结果来自真实证据，未知值留空；服务端build/与Python缓存不提交。

- [项目指南](SC6103_项目指南与三人分工.md)：要求、早期方案和最新分工更新。
- [详细文件/接口责任表](SC6103_三人详细分工与接口责任表.md)：逐文件归属、接口和独立验收。
- [接口规范v1.0](SC6103_接口与数据类型规范.md)：权威32字节头/DTO/操作与监控规则。
- [固定数据](experiments/seed_manifest.md)、[实际结果表](experiments/results.csv)、[报告总稿](report/项目报告.md)。
