# B 复查结果与 A/B/C 联调计划

日期：2026-10-07。B 是本文执行负责人。依据已冻结的 [接口规范 v1.0](../SC6103_接口与数据类型规范.md)、[逐文件分工](../SC6103_三人详细分工与接口责任表.md)及 main `2cc2e66d69f38237653297089406ba9ad0baaaf9`。

## 1. 现在可以确认什么

**B 的六业务、数据和监控已经完成独立实现；接下来优先让 A 打通通信入口，然后按阶段验收。** 当前文件中 A 的 codec、UDP、dispatcher、history、loss 等仍有占位方法，不能开始有效的完整联调。C 的客户端已交付。

| 范围 | 复查结论 / 证据 |
|---|---|
| B 业务与种子数据 | 既有 34 项 Java 测试通过；复查输入优先校验、错误无副作用、float 边界、不可变快照，未发现需要修改的业务缺陷 |
| B 监控 | 既有 15 项 Java 测试通过；保留替换、到期、只读剩余时间与 nanoTime 跨界处理 |
| 实验工具 | 本轮 27 项 Python 测试通过：17 项证据核对、4 项运行前检查、6 项故障代理测试；其中一个测试遍历 16 种 case/mode 组合 |
| runner | 补强端口冲突、真实只读就绪探测、代理就绪、证据核对、失败记录与进程清理；解析/预演及故障路径检查见 evidence/b |
| 完整 Java/Python 网络服务 | **未验收**；A 仍未实现，不把模拟结果计为网络通过 |
| 三机及 JDK 17 实际运行 | **待验收**；现有 Java 编译目标为 17，验证机器实际是 JDK 25.0.4 |

本轮重点优化：

1. 原 runner 从日志中取第一/最后一条详情回复；现在逐一核对 session、模式、请求 ID、操作、输入、阶段、顺序和真实响应，拒绝拿错或缺失的证据。
2. 原先只看终态可能漏掉未生效的故障；现在还检查逐次发送、超时和终态 attempts。全丢用例必须有对应目标的 5 条实际代理丢包记录。
3. 代理日志分别记录实际报文身份和故障目标身份，便于排查其他包，避免误把查询或其他 session 记成目标写请求。
4. 不再仅等固定 250ms 就启动客户端：先检查本例所用端口，再对自有 Java 进程做独立 session 的只读就绪查询，代理通过自己的 READY 日志确认。
5. 每次保留 `analysis.json`、`result.csv` 及原始日志，再追加总表；失败也留记录。结束仅清理 runner 自己创建的进程，清理/写表错误不会遮盖原始实验错误。

证据核对通过只写 `STATE_VERIFIED_NEEDS_A_LOG_REVIEW`。A 的 `businessExecuted/cacheHit/DROP_REPLY` 证据审核后才可填最终通过，不能用客户端重试次数代替服务器执行次数。

## 2. 分工保持，交接方式优化

现在无需再重新分配业务文件。三人按照现有文件归属工作，各自提交可验收版本；B 组织集成和记录，避免所有人同时修改服务器或实验驱动。

| 成员 | 接下来负责的文件 / 接口 | 独立完成后的交付 |
|---|---|---|
| A | `server/src/flight/BinaryProtocolCodec.java`：ProtocolCodec 编解码；`UdpTransport.java`：open/receive/send/close；`UdpServer.java`：run 与装配；`RequestDispatcher.java`：handle(ReceivedDatagram)；`InMemoryRequestHistory.java`：find/saveNew；`LossSimulator.java`：shouldDropReply；自己维护 ServerMain/启动说明与 A 测试 | 可监听的服务端、codec 向量验证、ALO/AMO 历史/冲突/缓存测试、实际执行/缓存/故障/callback 日志、A 报告章节 |
| B（你） | `SeedData.java`、`DefaultFlightService.java`、`InMemoryMonitorService.java`、内部 FlightValidation 和 `server/test/flight/b/`；维护 `experiments/` 和报告总稿 | 本轮 B 交付包、种子/验收表、统一实验入口、联调记录；业务缺陷只在 B 文件修复 |
| C | `client/protocol_codec.py`、`udp_transport.py`、`invoker.py`、`monitor.py`、`client.py`、`experiments.py` 与自己的 tests | 客户端与全套独立测试输出、请求向量、解析 Java 回复/callback 的验证；匹配/时限/显示问题只在 C 文件修复 |

共享接口保持原签名和 v1.0 字段；修改契约确实不可避免时，先提交具体差异和受影响文件清单，全组一次确认。正常实现和修复不需要每一步沟通。

**给 A 最重要的 4 条：** A/B 共用同一 monitor 实例；AMO 在调用 B.handle 前拦截缓存命中；发监控确认时只读刷新原登记 remainingMillis；普通订座回复被丢弃或发送失败，仍尝试有效 callback。完整交接见 [B_HANDOFF](../server/B_HANDOFF.md)。

**给 C 最重要的 3 条：** 固定测试航班 1001 初态 10 座/100 SGD；runner 的加价参数是 20，不能依赖 CLI 默认 10；监控期间菜单阻塞，双监控实验用额外客户端进程订座即可。

## 3. 第一件事：让队友拿到同一份版本

本轮 B 代码、测试和文档已纳入 `main`，队友直接从主分支获取；`codex/b-flight-service-and-tests` 保留交付记录。本地 `D:\ntu\103\groupwork` 是文件镜像，没有 `.git`，不能直接在此执行 pull/push。

本轮 B 交付已集成；每次联调前先确认同一个 main 提交，并冻结一次集成 commit。可在另一个目录做正式 Git clone，保留当前镜像。每人记录自己的提交号，B 记录集成提交号；测试期间不混用“最新文件”和旧编译产物。

- A 先合入可监听的通信入口，随后分派/历史/故障处理逐项完成。
- B 交付只包含自身变更的源码、测试、实验工具和文档，排除 server/build、Python 缓存与 .backups。
- C 原有文件保留；只在真实联调发现 C 问题时更新，并重新提交其相关测试。
- 不直接复制整套旧镜像覆盖队友的新文件。每人更新自己的目录；共同文档由 B 合并。

正式 Git checkout 切换到 main 后执行 git pull --ff-only origin main；三人记录并使用同一集成提交。后续交付默认更新 main，涉及共享契约时按第2节协调。

## 4. 每人先自行通过的门槛

| 门槛 | A / B / C 各自做什么 | 进入下一阶段的条件 |
|---|---|---|
| A codec | 用 C 的 `evidence/c/python-request-vectors.json` 与 `client/tests/protocol_vectors.json` 验证大端、UUID、32字节头、长度、错误体；对 malformed/未知操作/模式错误做独立测试 | 有可复现输出；能解析 Python 请求并生成 C 能解析的回复/callback |
| A 运行 | build、正常 bind/run、种子加载、空闲循环；接口装配同一 monitor；关闭后端口释放 | 无生产占位异常；1001只读查询返回正确初态 |
| A 语义 | ALO重复进入业务；AMO成功/业务错误缓存、同键异字节/异peer冲突、模式检查先于历史；监控缓存刷新 | 提供独立测试和每次业务调用/缓存重放的日志 |
| B | 六业务、种子、监控的49项独立测试；本轮27项工具测试 | 无失败；完整复制文件仍可运行 |
| C | 运行现有 tests；导出请求向量；确认菜单/CLI参数、日志、unknown与监控期限 | 自测通过；C HANDOFF 中的剩余条件明确 |

从仓库根目录运行：

```powershell
.\server\test-b.ps1 -EvidenceFile evidence/b/b-self-tests.txt
python -m unittest experiments.test_analyze_results experiments.test_runtime_check experiments.test_udp_loss_proxy -v
python -m unittest discover -s client/tests -v
python -m client.tests.export_vectors
```

向量导出命令把 JSON 输出到控制台；需要存档时显式重定向到新证据文件，不覆盖 C 已提交的历史证据。A 自己的测试命令由 A 补到 server/README，B 不猜测一个尚不存在的入口。

## 5. 联调一：先同一电脑打通业务

**主持 B，A 运行并检查服务端，C 检查客户端解码。建议 30–45 分钟。** A 核心代码完成后开始，先不注入丢包。

1. 三人确认集成 commit、v1.0、seed_manifest 和实际 Java/Python 版本。
2. B 顺序跑 baseline 的 AMO/ALO；runner 每次启动新服务端复位，不能同时运行多个 runner 写同一 results.csv。
3. 正常基线：英文路线 `[1001,1002]`；1001 初态10座/100；订座1后9座；SET120再INCREASE20后140；监控确认并安静结束。
4. 用菜单补中文路线 `[1004,1005]`、无路线 status1、航班9999 status2、1003订座 status3、1001订11座 status3；失败后查询状态未变。
5. 结构正确但业务非法的数量0、负价格、duration0、NaN等，正常菜单会在本地拒绝，不能把菜单提示当服务器错误码验证。由 A 的测试发送器构造结构正确的非法值，核对 status4 和业务无副作用；B提供期望，C不必取消生产输入校验。

```powershell
.\experiments\run_suite.ps1 -Case baseline -Semantics amo
.\experiments\run_suite.ps1 -Case baseline -Semantics alo
```

Python 不在 PATH 时加 `-Python '完整的 python.exe 路径'`；端口被占用时换 `-Port 16889`，不要结束不属于自己的服务端。

**退出条件：** 六操作的真实跨语言成功体正确，常见错误码正确，业务错误无副作用；保留两模式证据。失败按第8节归属，修复后只重跑失败用例及直接受影响用例。

## 6. 联调二：回调、时序及调用语义

**建议分两个固定窗口，总计 60–90 分钟。** 先做回调，再做丢包。以下测试均要求 A 核心实现已完成。

### 6.1 单/双监控

先启动干净 AMO 服务端，在同一电脑用多个终端即可。所有终端从仓库根目录运行，默认生成不同 session：

```powershell
# 服务端终端，A
.\server\build.ps1
java -cp server/build/classes flight.ServerMain --bind 127.0.0.1 --port 6789 --semantics amo
```

```powershell
# 监控终端 M1，C 操作
python -m client --server 127.0.0.1 --semantics amo --case monitor --flight-id 1001 --monitor-seconds 20 --log-file evidence/b/joint/monitor-M1.jsonl
```

```powershell
# 订座终端 W，B 操作菜单：3 → 1001 → 1 → 0
python -m client --server 127.0.0.1 --semantics amo --log-file evidence/b/joint/writer.jsonl
```

必须等 M1 显示“监控已确认”再订座。首次应收到航班1001、余座9、seq1。callback 使用 M1 的登记 session/requestId，不是 W 的订座身份。

| 测试 | 谁操作 | 具体步骤 / 验收 |
|---|---|---|
| 单监控 | C开M1，B订座，A查日志 | 正常事件一次；到期退出；之后订座不再向已到期登记发事件 |
| 双监控 | C开M1/M2，B另开W，A查日志 | M1/M2都监控1001，分别确认后W订座；两个不同登记收到同余座/seq |
| 航班隔离 | 同上 | 复位，M1监控1001，M2监控1002，W订1001；只有M1收到 |
| 安静到期与清理 | C开2秒监控，A观察 | 不订座；客户端准时返回；服务端空闲清理周期不超过250ms，清理容器由 A 测试证明 |
| 同session替换 | A测试发送器，B核对 | 同flight同session新requestId登记；旧key立即inactive/remaining0，新key有效 |
| 丢监控确认 / AMO重放 | A故障发送器，C客户端，B记录 | 同身份重试，不重复业务、不续期；确认剩余时间减少；过期/被替换原登记重放返回remaining0 |
| 确认前callback / 乱序重复 | A/C时序测试，B记录入口 | C仅在确认后显示已暂存最大seq；无确认则放弃；重复确认与无关包不能延长deadline |
| 普通回复丢失/发送失败 | A注入，B订座，C监控 | 本次有效事件仍尝试发送；AMO重传不再次扣座、不再生成业务事件；一个接收者发送失败不阻断其他接收者 |

Callback 本身是 best effort，无ACK或重传。基础无故障回调验证应收到；故障场景中必须区分 A 是否尝试发送与网络是否送达，不能要求 UDP 保证零丢失。

### 6.2 受控丢包矩阵

由 B 在一台电脑顺序跑；A审核目标写请求的 execution/cache/drop 日志；C仅在客户端异常时处理。全部8种case各跑ALO/AMO，共16次；每次独立复位。

```powershell
foreach ($caseName in @('baseline','request_loss_reserve','reply_loss_reserve','reply_loss_increase','reply_loss_set','all_request_loss','all_reply_loss','monitor')) {
    foreach ($modeName in @('alo','amo')) {
        .\experiments\run_suite.ps1 -Case $caseName -Semantics $modeName
    }
}
```

出现异常暂停矩阵，保留该例记录，定位后再跑后续例。全丢案例虽然客户端退出1，runner仅在“unknown + 正确只读终态 + 5次尝试 + 5条代理故障证据”全部满足时视为预期情形。

重点对比：

| 情形 | ALO | AMO | 必须额外查看的证据 |
|---|---|---|---|
| 首次订座回复丢失 | 最终余座8，业务2次 | 余座9，业务1次/缓存1次 | A确实丢首次目标回复；C尝试2次 |
| 首次加价回复丢失 | 票价140，业务2次 | 120，业务1次/缓存1次 | delta20；不能用默认10 |
| 首次SET回复丢失 | 票价120，业务2次 | 120，业务1次/缓存1次 | 终态相同，执行/缓存日志才能区分 |
| 全部目标写请求丢失 | 余座10，业务0次 | 同左 | 代理丢请求5次；写unknown，之后新查询成功 |
| 全部目标写回复丢失 | 余座5，业务5次 | 余座9，业务1次/缓存4次 | 代理丢回复5次；写unknown，之后查询成功 |

正常 baseline 的写ID是3/4/5；单写故障例写ID为2。就绪探测有单独的session，只读查询，不计入目标写操作统计。**不能全局数日志行数，也不能把查询算进“订座执行次数”。**

AMO请求键冲突、peer变化、业务错误缓存、模式不匹配、坏长度/未知操作等，不在上述16个正常CLI驱动用例内。A使用测试发送器覆盖并保存结果；涉及客户端过滤的异常回复由C已有/补充测试覆盖。结果表保留对应独立测试入口，不能把16次runner当作整个协议全部验收。

## 7. 联调三：三台电脑与提交演练

前两轮通过后开始。A电脑运行Java服务端；C电脑开M1；B电脑开M2或写客户端。连接同一可互通局域网，用服务端真实IPv4，服务端绑定0.0.0.0。

双监控时在B电脑另开W进程；三台电脑上可以有多个客户端进程。只需要窗口安排，不需要C额外开发并发菜单。

按 [demo_steps.md](demo_steps.md)演练：六业务 → 单监控 → 双监控 → 航班隔离 → 到期 → 两种语义对比。首次回复丢失可在三机上直接由A/C选择器注入；全丢代理用例保留本地受控证据，区别记录。

验收记录三台电脑实际IP、Java/Python版本、集成commit、完整命令、模式/session/requestId、两端日志及截图。不要把ping通当成UDP应用通；最后实际执行查询与回调。按需允许课程用UDP端口入站，不全局关闭防火墙。

最终从新目录拿源码、按README编译启动，排除依赖已有build产物才能运行的问题；至少一台实际JDK17环境复核，Python3.10+。三人各自讲自己的模块并解释一个失败场景。代码注释、报告、实际贡献比例与证据合并后再按老师提交渠道打包。

## 8. 出错时只交一个完整问题包

先由B分类，把一份问题交给责任人；A/C可以独立复现，不必实时追问每一个参数。

| 现象 | 优先负责人 | B提供的线索 |
|---|---|---|
| 无监听/端口问题/包长或大端错误/坏reply | A | 服务端stderr、命令、Python encodedHex、模式、peer |
| AMO重复扣座、同键冲突不报错、缓存/模式次序错误 | A | 精确session:requestId、相同/不同原始字节、peer、执行/cache日志 |
| 解码输入正确，但返回余座/票价/错误码/事件名单错误 | B | REQUEST_CREATED输入、handle调用结果、前后状态及B测试入口 |
| A已发送正确callback，但C不显示、身份/顺序过滤或期限错误 | C | callback实际字节、登记身份、来源地址、C日志和MONITOR_START/END |
| callback没发或发送被普通reply失败中断 | A先查发送链；B查事件产生 | ServiceResult事件身份、isActive结果、A发送/drop日志 |
| 客户端业务错误/unknown显示混淆、重试身份变化 | C | 请求十六进制、各attempt与终态；B明确未知后只查询 |
| 代理/取证脚本错误、总表不完整 | B | proxy.jsonl、analysis.json、result.csv、原始client/server日志 |

复制此模板到小组Issue或文档即可，本文不会替你自动发消息：

```text
用例 / 模式：
集成commit / 三方版本：
环境与命令：
session / requestId / operation / flightId：
客户端与服务端peer：
预期结果：
实际结果（成功/业务错误/unknown）：
真实前后状态 / attempts / execution / cacheHit：
证据目录与最短复现步骤：
初步负责人：A / B / C；修复提交与回归结果：
```

重试耗尽的写操作不能换新ID自动补做。先发新只读查询核对终态，保留unknown，再决定是否由使用者明确执行新的业务。

## 9. 后续时间安排

以下按当前10月7日规划，最终课程日期以老师通知为准；原课程材料规定10月14日午夜提交、10月17日演示。为了避免“午夜”理解偏差，内部按**10月13日晚前完成可提交包**。

| 时间 | A | B（你） | C | 共同检查点 |
|---|---|---|---|---|
| 10/7–10/8 | codec/UDP/正常run与query；继续dispatcher/history | 分享本轮B交付，确认种子/用例，准备记录表 | 跑已有自测，交请求向量与日志示例 | 三人可拿同一代码；A基础查询ready |
| 10/9 | 完成ALO/AMO、故障、callback、独立测试 | 执行联调一；按归属登记问题 | 处理真实跨语言解码/菜单问题 | 六业务、常见错误、两模式通过 |
| 10/10–10/11 | 修复语义/发送问题，审核目标日志 | 主持联调二、跑16例、汇总真实证据 | 监控/重试/过滤相关回归 | 回调组与丢包矩阵验收 |
| 10/12 | 服务端电脑与A讲解/章节 | 主持三机、汇总报告 | 客户端电脑与C讲解/章节 | 三机可复现；姓名/比例补齐 |
| 10/13 | 干净构建/检查A源码注释 | 检查报告、证据、提交包 | 干净客户端/检查C注释 | 冻结最终commit与可提交包 |
| 10/14前 | 按老师渠道共同确认提交 | 记录提交回执 | 共同检查 | 不在截止前引入未验收功能 |
| 演示前 | 各自熟悉问答 | 备份包与固定数据演练 | 各自熟悉问答 | 一次完整演练 |

若A基础通信晚于10/8，先把时间投入核心互操作，推迟可选界面/额外功能，保留回调、两种调用语义、受控丢包和三机这些必须项。不要用B或C模拟测试填补整套服务尚未通过的空白。

## 10. 你作为 B 的下一步清单

1. 把本轮B代码/测试/文档交给队友，约定集成commit；让A阅读B_HANDOFF并先交“可监听+能查1001”的版本。
2. 请C提供现有测试输出和请求向量；客户端实现不用重新分配，C继续自己维护。
3. A核心完成后，你按本计划主持三轮联调，顺序运行runner、保存证据并分类问题；队友修自己模块。
4. A审核后把实际 businessExecutions/cacheHits 和最终结论填写到results.csv；保留最初NOT_EXECUTED行与失败历史，后续记录追加，不抹掉失败。
5. 合并三人报告章节、正式姓名、实际贡献比例与实验结论；最终包从干净目录复现。

现在的优先事项是**交付B版本 → A打通通信 → 第一轮真实业务测试**。B不需要继续扩展业务功能来等待A。
