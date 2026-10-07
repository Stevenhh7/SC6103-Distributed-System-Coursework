# Python UDP 航班客户端

负责人：C。Python 3.10+，仅标准库。实现依据为 [接口规范 v1.0](../SC6103_接口与数据类型规范.md) 和 [最新详细分工](../SC6103_三人详细分工与接口责任表.md)。

已实现六操作菜单、手工二进制 codec、UDP/IPv4、有限重传、请求丢失注入、监控回调、实验入口和证据日志。客户端独立测试通过；当前仓库 Java 服务端核心仍是占位方法，真实 Java 联调、三机验证待 A/B 实现后进行。职责与剩余事项见 [TODO](TODO.md)。

## 启动与自测

从**仓库根目录**运行，勿直接运行 client/client.py：

~~~powershell
python -m client --help
python -m client --check
python -m unittest discover -s client/tests -v
python -m client --server 127.0.0.1 --port 6789 --semantics amo
~~~

服务器完成后，最后一条命令提供 1..6 六操作及 0 退出。跨电脑使用服务端实际 IPv4 地址；客户端与服务端模式须一致。监控期间暂停菜单，自动到期后恢复。EOF 正常退出；Ctrl+C 中断并关闭 socket。中断不会取消服务端已经执行的操作。

--check 只检查配置和装配，不解析 DNS、不打开 socket，不代表业务或网络联调通过。测试采用模拟传输和真实 127.0.0.1 UDP 应答器；应答器仅在测试线程运行。

## 文件与调用关系

| 文件 | 职责 |
|---|---|
| client.py、__main__.py | CLI、六操作菜单、退出清理 |
| config.py | 启动及本地实验配置 |
| protocol.py、models.py | v1 常量及不可变 DTO，公共字段保留 camelCase |
| protocol_codec.py | encode_request / decode_message；仅 float32 用 struct |
| udp_transport.py | 同一 AF_INET socket；固定解析端点；65535 字节接收 |
| invoker.py | 分配身份、编码一次、有限重传、匹配回复、暂存回调 |
| monitor.py | accepted_monitor 建立截止时间；monitor_until_expiry 过滤并显示回调 |
| input_validation.py、presentation.py | 菜单/实验共享输入校验与结果显示 |
| loss_simulator.py | 指定 RequestKey 只丢首次请求 |
| experiments.py、event_log.py | 同一 Invoker 驱动实验；本地 JSON Lines 日志 |
| tests/ | 固定向量、可控时钟、模拟传输、真实本机 UDP、菜单和实验测试 |

## 调用与监控约定

- 默认每次尝试 1000ms、最多 5 次（含首次）。重传的 session、requestId、原始字节、源端口全部不变。
- 发送也有超时上限，不继承上次接收缩短后的超时值；发送超时消耗本次尝试，继续等剩余时间，耗尽同样返回结果未知。
- 只接收来自解析后的服务端 IP/端口、且身份/op/mode 匹配的回复。业务错误立即结束；status=7 的模式错误也能正确显示。
- 无关、畸形、迟到报文和回调不会重置当前尝试的绝对截止时间。
- 耗尽显示“未获得确认，执行结果未知”。不自动换新 ID 再订座/加价。可以显式发起新的查询确认状态。
- requestId 达到 i32 上限后拒绝新调用并退出；以**新的 UUID**重启。正常启动自动生成 UUID v4；固定 UUID 只供受控实验使用。
- 首次监控成功确认的接收时间 + remainingMillis/1000 为本地截止时间；重复确认不续期，0 立即结束。
- 确认前仅暂存当前登记最高序号 callback，确认后才显示。监控只显示严格递增序号，不要求从 1 连续开始。错误/最终超时清空暂存。
- 地点仅修剪 U+0020 空格，严格 UTF-8；价格先转 float32 再检查范围。拒绝 NaN、Infinity、溢出和转为 float32 后为 0 的 delta。
- Invoker/monitor 设计为同一线程使用；菜单不会并行发起第二个调用。socket 不向其他线程共享。

## 参数

| 参数 | 默认/规则 |
|---|---|
| --server / --port | 127.0.0.1 / 6789 |
| --semantics | amo，也可 alo |
| --timeout-ms | 1000，正整数 |
| --max-attempts | 5，正整数，包含首次 |
| --session-id | 默认随机非零 UUID；固定值不能被两个客户端共用 |
| --drop-first-request | UUID:requestId；须同时提供相同 --session-id |
| --check | 离线配置/装配检查 |
| --verbose | stderr 输出详细 JSON Lines 事件 |
| --log-file | 将事件追加到指定 UTF-8 文件，自动建立父目录 |
| --case | 见下方实验表 |
| --flight-id | 使用 --case 时必须显式指定 B 发布的真实 ID |
| --source / --destination | baseline 必填，来自 B 的路线数据 |
| --quantity / --new-price / --delta | 实验参数，默认 1 / 120.0 / 10.0 |
| --monitor-seconds | 实验监控时长，默认 5，范围 1..3600 |

退出码：0 正常结束/帮助/检查；1 网络错误、实验未全部确认或编号耗尽；2 CLI 参数非法；130 用户中断。交互菜单中的单次业务错误/未知不会强制结束进程。实验退出 0 仅说明这些客户端调用取得成功确认，**不证明**服务端执行次数或全组验收通过。

## 实验入口

每个独立用例前由 **B 重启整个 Java 服务端**，复位航班、历史、订阅和序号。客户端没有 RESET 操作，也不会自行重启其他成员程序。

| case_name | 客户端操作 |
|---|---|
| baseline | 初态详情 → 路线 → 订座 → 设置票价 → 加价 → 监控至到期 → 终态详情 |
| request_loss_reserve | 初态查询 → 丢写操作首次请求 → 同 ID 重传订座 → 终态查询 |
| reply_loss_reserve | 初态查询 → 订座 → 终态查询，首次回复丢失由 A 注入 |
| reply_loss_increase | 初态查询 → 加价 → 终态查询，首次回复丢失由 A 注入 |
| reply_loss_set | 初态查询 → 设置票价 → 终态查询，首次回复丢失由 A 注入 |
| monitor | 初态查询 → 登记监控并等待 → 终态查询，便于另一独立客户端订座 |

故障用例的新进程中：初态查询 ID=1、目标写操作 ID=2、终态查询 ID=3；重传不会占新 ID。request_loss_reserve 自动选中写请求；若显式传选择器，也必须与它一致。reply_loss_* 不自动丢回复，必须由 A 设置相同 UUID:2。初态查询失败则停止写操作。写操作未知后只做明确的终态查询，不再补做写操作。baseline 中途出现业务错误或未知时也停止后续写操作、采集终态；查询成功不会把此前未知的写操作改成已确认。

下面的 1001、SIN/PEK 是命令示例，**须替换为 B 的实际种子数据**：

~~~powershell
python -m client --semantics amo --case baseline --flight-id 1001 --source SIN --destination PEK --log-file evidence/c/baseline.jsonl

python -m client --semantics amo --session-id 00112233-4455-4677-8899-aabbccddeeff --case request_loss_reserve --flight-id 1001 --log-file evidence/c/request-loss-amo.jsonl

python -m client --semantics amo --session-id 00112233-4455-4677-8899-aabbccddeeff --case reply_loss_reserve --flight-id 1001 --log-file evidence/c/reply-loss-amo.jsonl

python -m client --case monitor --flight-id 1001 --monitor-seconds 60 --log-file evidence/c/monitor.jsonl
~~~

reply_loss_reserve 示例要求 A 将 --drop-first-reply 设为 00112233-4455-4677-8899-aabbccddeeff:2。改用 alo 时两端一起改，且先重启服务端。不要把受控情况下“ALO 两次、AMO 一次”的预期当作真实结论；对照实际尝试数、终态和 A 的执行/缓存日志。

baseline 是一个客户端的六操作驱动，双监控/航班隔离需 B 安排多个独立客户端和触发订座。每个 monitor 进程自动有独立 UUID；要给两名监控者同时触发更新，可另开一个短时订座进程。回调本身没有 ACK/重传保证。

全部请求丢失和全部回复丢失已由客户端测试故障对象覆盖，生产 CLI 的首次丢包开关不能用于“全丢”。真实全回复丢失实验还需 A 的测试注入，并按指定请求键丢弃普通回复，不丢初态/终态查询和 callback。

## 证据与交接

--log-file 保存 REQUEST_CREATED（调用输入、实际编码十六进制、超时及尝试上限）、SEND、SEND_TIMEOUT、DROP_REQUEST、ATTEMPT_TIMEOUT、REPLY（含实际响应字段）、RESULT_UNKNOWN、CALLBACK、MONITOR_START/END、CASE_STEP 等事件。CASE_START 保存数量、价格、监控时长等完整实验参数。JSON 仅用于本地日志；线上保持规范二进制。客户端无法得知 cacheHit/businessExecuted，必须由 A 的日志补充。

- [二次复核与逐项需求映射](AUDIT.md)
- [复核后的 63 项验证记录](../evidence/c/2026-10-07-client-audit-unittest.txt)
- [首次实现的 51 项记录](../evidence/c/2026-10-07-client-unittest.txt)
- [六个 Python 编码请求向量](../evidence/c/python-request-vectors.json)
- [交接清单](HANDOFF.md)
- [C 报告章节](../report/C_客户端与跨语言.md)

重新生成向量：python -m client.tests.export_vectors。规范原始 8 个向量保存在 tests/protocol_vectors.json，来源为接口规范第 10 节；它们是协议样例，不是业务运行证据。
