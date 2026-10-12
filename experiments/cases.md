> **2026-10-10 实测更新：** 下面保留 B 在 10-07 的用例设计和历史状态。A 已完成；16 个 ALO/AMO 组合均通过真实 Java 17 本机 UDP 验证，实际结果见 [最终 CSV](../evidence/a/release-java17/matrix/results.csv)。200 组自动化测试通过，三机未执行。
>
> 推荐跨平台入口：`python3 -m experiments.verify_all --matrix`；只运行实验：`python3 -m experiments.run_suite`；单例：`python3 -m experiments.run_suite --case reply_loss_reserve --mode amo`。Windows 将 python3 改为 python。新入口直接核对 A 日志，无需人工猜测执行次数。PowerShell 专用入口本次未在 Windows 上验证。

# B 实验用例与验收标准

日期：2026-10-07。B 负责用例、复位、证据和报告整合；A 提供服务端执行次数/缓存命中；C 提供既有 `run_case`/CLI 与客户端日志。

目前 B 的 49 项 Java 独立测试和本轮27项实验工具测试通过。**A 的核心代码仍为占位，以下真实 Java/Python 网络用例未执行**。结果表空值不是零，不用期望值填入实际结果。分阶段合作见[B复查与联调计划](B_复查与队友联调计划.md)。

## 1. 启动与复位

从仓库根目录运行。安装 Java 17+ 与 Python 3.10+；编译使用 `--release 17`。本次实际验证环境是 JDK 25.0.4，不能据此声称已经在 JDK 17 运行过。

```powershell
.\server\test-b.ps1 -EvidenceFile evidence/b/2026-10-07-b-self-tests.txt
python -m unittest experiments.test_analyze_results experiments.test_runtime_check experiments.test_udp_loss_proxy -v
.\experiments\run_suite.ps1 -Case reply_loss_reserve -Semantics amo -DryRun
```

A 完成通信层后执行真实单例：

```powershell
.\experiments\run_suite.ps1 -Case baseline -Semantics amo
.\experiments\run_suite.ps1 -Case request_loss_reserve -Semantics alo
.\experiments\run_suite.ps1 -Case reply_loss_reserve -Semantics alo
.\experiments\run_suite.ps1 -Case reply_loss_reserve -Semantics amo
.\experiments\run_suite.ps1 -Case reply_loss_increase -Semantics alo
.\experiments\run_suite.ps1 -Case reply_loss_increase -Semantics amo
.\experiments\run_suite.ps1 -Case reply_loss_set -Semantics alo
.\experiments\run_suite.ps1 -Case reply_loss_set -Semantics amo
.\experiments\run_suite.ps1 -Case all_request_loss -Semantics amo
.\experiments\run_suite.ps1 -Case all_reply_loss -Semantics alo
.\experiments\run_suite.ps1 -Case all_reply_loss -Semantics amo
```

也应执行未列出的 ALO/AMO 组合。Python 不在 PATH 时使用 `-Python '完整的 python.exe 路径'`。每次 runner 启动自己的 Java 服务端，使用一个新 session，保存 client/server/proxy 日志；结束只停止它创建的进程，不操作其他 Java 程序。当前 A 占位检测会直接报“未执行”，不会新增通过记录。

默认 Java 端口 6789，全丢代理端口 6790，均绑定本机。runner先检查端口，再用单独session只读查询等待Java就绪，代理按READY日志确认；占用或启动失败保存失败记录。已有服务端占用同端口时先正常结束自己的服务端或指定其他 `-Port`，不要让多个实例共享实验。runner顺序执行，不并发追加同一results.csv。不要用本机地址进行三机验收。

## 2. 受控状态预期

初态均为 1001 余座=10、票价=100、序号=0。最多 5 次尝试，1 秒/次。表中数量预期要求除指定故障外的请求/回复均正常送达，且 server 顺序处理。

| 外部 case | 故障 | ALO 最终状态/执行次数期望 | AMO 最终状态/执行次数期望 | 客户端 |
|---|---|---|---|---|
| baseline | 无 | 余座9、票价140；订座/SET/INCREASE 各1次 | 同左 | 六操作成功；monitor 安静到期 |
| request_loss_reserve | C 丢首次写请求 | 余座9，订座执行1次 | 同左 | 同 ID 重传后成功 |
| reply_loss_reserve | A 丢首次写回复 | 余座8，订座执行2次 | 余座9，执行1次、重放1次 | 第2次尝试确认 |
| reply_loss_increase | A 丢首次加价回复 | 票价140，加价执行2次 | 票价120，执行1次、重放1次 | 第2次尝试确认 |
| reply_loss_set | A 丢首次设置回复 | 票价120，SET 执行2次 | 票价120，执行1次、重放1次 | 终态相同，需日志区分执行次数 |
| all_request_loss | 代理丢目标写请求全部5次 | 余座10，执行0次 | 同左 | 写操作未知；随后新只读查询成功 |
| all_reply_loss | 代理丢目标写回复全部5次 | 余座5，订座执行5次 | 余座9，执行1次、重放4次 | 写操作未知；随后新只读查询成功 |
| monitor | 无 | 余座10、票价100 | 同左 | 登记成功并按剩余期限返回 |

写请求目标为新实验进程 `session:2`：ID=1 查询初态，ID=2 写操作，ID=3 查询终态。baseline 的 ID 不相同：详情1、路线2、订座3、SET4、INCREASE5、监控6、终态详情7。

“执行次数”指业务入口对这个目标写请求的实际执行次数，不是全例所有查询的次数。不能用客户端 attempts 代替执行次数，不能仅凭 SET 最终票价推断去重是否发生。

runner核对真实初态/终态、逐请求session/mode/ID/op/输入/阶段顺序、成功或unknown、发送与超时次数；全丢还要求5条对应目标的代理丢包证据。输出analysis.json、每例result.csv和总表，写入 `STATE_VERIFIED_NEEDS_A_LOG_REVIEW`。A 的日志review完成后，B才补真实execution/cacheHits、目标DROP_REPLY和结论。若出现额外网络故障，保留实际日志，标失败或未完成，不强行套用表中数字。baseline含3个写请求，mutation_attempts单列留空，各操作真实attempts见client.jsonl。

## 3. 全丢故障代理

现有首次丢包开关不用于全丢。`udp_loss_proxy.py` 是 B 的本地实验工具，通过外部代理只丢指定 session/requestId 的普通写请求或回复；初态/终态查询、其他身份与 callback 正常放行。不修改生产协议、A 的语义实现或 C 的调用器。

全丢用例复用 C 的 `reply_loss_reserve` 驱动，仅使用“查询—订座—查询”的调用流程；真实故障名称以外部 runner case 和 proxy 日志为准。该驱动本身不会注入服务端回复故障。

代理每例只接收一个客户端源端点。它给 Java 提供稳定的后端 UDP peer，因此 AMO 的 peer 检查仍有效；不可将它拿来做双客户端/源端点冲突实验。跨机器监控使用直接通信。

手动示例（两个终端，server 已按 AMO 启动）：

```powershell
python -m experiments.udp_loss_proxy --listen-port 6790 --server-port 6789 --session-id 11111111-1111-4111-8111-111111111111 --request-id 2 --drop replies
```

```powershell
python -m client --server 127.0.0.1 --port 6790 --semantics amo --session-id 11111111-1111-4111-8111-111111111111 --case reply_loss_reserve --flight-id 1001 --quantity 1 --log-file evidence/b/manual/client.jsonl
```

预期客户端退出码 1 是此例的“写操作结果未知”，不能把它改成成功；终态查询与 A 日志才能确认实际状态。代理测试目前6项，包含真实回环UDP行为与日志身份回归，它们只证明故障工具行为，不证明Java互操作。proxy日志中sessionId/requestId表示实际报文，targetSessionId/targetRequestId表示故障选择器。

## 4. 多客户端、监控与错误边界

| 用例 | 步骤 | 验收 |
|---|---|---|
| 一个监控者+一个订座者 | 客户端 M 监控1001，收到确认后客户端 R 订座1 | M 收到1001余座9、seq1；callback 身份=M登记，不是 R |
| 两个监控者 | M1/M2 都登记1001，另开辅助订座进程 | 两个登记都收到同次更新；seq/余座一致；不同 session/peer |
| 航班隔离 | M1 监控1001，M2 监控1002；辅助进程订座1001 | 只有 M1 收到事件；M2 仍按期限结束 |
| 无事件到期 | 监控2秒，期间不订座 | 客户端结束；B 查询失效；A 空闲循环清理 |
| 同 session 新登记 | 对1001用不同 requestId 连续登记 | 旧 RegistrationKey 立即失效，剩余0；新登记有效 |
| AMO 重放确认 | 丢首次监控确认并延迟重传 | A 不重执行业务；刷新原登记剩余时间；不延长 deadline |
| 旧登记过期/被替换后重放 | 使用测试报文重放原身份 | A 返回原成功+剩余0，不使用新登记的时间 |
| 确认前 callback | 网络测试使事件先于确认到达 | C 暂存最高序号，确认后显示；最终未确认则放弃 |
| 丢订座回复仍回调 | M 先登记；R 写回复丢失 | 业务有效；A 仍发送本次事件；AMO 重传不再生成事件 |
| 错误无副作用 | quantity0/超余座、无航班、非法价格/时长 | 正确错误码；无扣座/改价/登记/序号增长/事件 |
| 乱序与连续无关包 | 测试重排 callback/重复确认/无关包 | C 显示序号递增，绝不延长原截止时间 |

后五类时序、重放和身份异常不能全靠正常菜单生成，应结合 A/C 自测与测试报文，在最终结果表中标明测试入口。不能为此增加生产网络 RESET/CANCEL 等操作。

## 5. 实际结果的填写

`results.csv` 初始行均 NOT_EXECUTED，状态和次数为空。独立 Java/代理测试结果另见 evidence/b，不把它们写成网络用例通过。

每例保存 mode、session、flightId、真实前后状态、客户端 attempts/unknown、A 的 businessExecutions/cacheHits、故障日志、执行命令和环境。失败/未知记录也保留。B 汇总后按证据写结论，三机记录注明三台电脑与实际 IPv4。
