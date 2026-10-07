# C：客户端与跨语言通信

实现日期：2026-10-07。负责人姓名待填写。本章记录 C 已完成的客户端与独立验证；真实 Java 服务端互操作、语义实验和三机结果尚待联调，最终由 B 整合。

## 1. 模块与接口

客户端使用 Python 3.10+ 标准库。控制台将输入转换成既定不可变 DTO，通过 Invoker.invoke(operation, body) 调用。Invoker 组装 Header，使用 encode_request 生成完整报文，交给 UdpTransport 发送；接收后用 decode_message 区分 Reply 和 CallbackMessage。

本次保留规范中的公开函数签名、CallOutcome 与 AcceptedMonitor 字段。新增的 ExperimentConfig、输入校验、显示和事件日志模块只影响本地组织，不改变协议。

协议头固定 32 字节，UUID 使用原始 16 字节，多字节整数手工大端编码；浮点仅使用单个 struct.pack/unpack('>f')。解码严格检查版本、类型、身份、保留位、总长度、bodyLength、UTF-8、数值与尾字节。错误回复根据 status 先选 ErrorBody，不误按成功结构解析。

地点只去除两端 U+0020，大小写保持；输入价格先舍入为 binary32 再判断范围。成功时间使用年/月/日/时/分五个 i32，显示 UTC+8。

## 2. 调用生命周期

每个客户端启动生成独立 UUID v4；同一进程保持一个 IPv4 UDP socket。服务端主机名只在打开传输时解析，发送和来源校验使用同一固定 IP/端口。

新逻辑调用分配递增 requestId，完整请求只编码一次。默认最多 5 次发送尝试、每次 1000ms；重传字节、身份和源端口保持不变。ID 达上限后拒绝新调用，要求结束当前进程后使用新 UUID，避免历史键回绕。

每次尝试建立单调时钟绝对截止时间，只将剩余毫秒传给 receive。接收来源错误、旧身份、错误操作/模式、坏包或 callback 都不会重新给一个完整超时周期。成功或业务错误均结束普通调用，包含服务端模式不匹配错误 7。

二次复核补齐发送边界：send 每次重设有限超时上限，避免沿用上一次接收剩余超时；发送超时消耗当前尝试，继续等待原截止前剩余时间，并保留同一请求身份重试。

尝试耗尽时，CallOutcome 的 timed_out=True，reply、reply_received_at 和 pending_callback 均为空。界面显示“未获得确认，执行结果未知”；不会自动用新 ID 再做一次订座/加价。接收超时无法证明服务端未执行。

客户端没有实现 ALO/AMO 服务端执行保证：其责任是携带所选模式、保持请求身份并正确解释回复；去重与执行次数须由 A 的服务端实现和日志证明。

## 3. 监控生命周期

监控登记等待确认时，若 callback 先到，Invoker 仅保留同一 session、登记 requestId、flightId、mode 的最高序号事件，暂不展示。登记失败或最终未知时清空暂存。

收到首个成功确认时立即记录 reply_received_at；accepted_monitor 使用该时间加 remainingMillis/1000 计算 deadline_monotonic。展示菜单/结果耗时不延长截止值。重复确认、无关包、乱序事件不能续期；remainingMillis=0 或已过期立即结束。

监控继续复用原 socket，只显示大于已显示序号的事件，允许首次序号大于 1。无事件时仍靠剩余超时到期退出。监控期间菜单暂停，避免两个循环争抢 socket。callback 无 ACK/重传保证；显示缺失序号不意味着需要客户端补发请求。

## 4. 故障注入与实验驱动

LossSimulator 按 UUID:requestId 仅跳过第一次 send，仍计一次尝试并正常等超时。它不影响回调接收。

实验入口 run_case 复用同一 Invoker，支持详细分工中约定的五个用例名，另有 monitor 辅助入口。故障用例先查询初态，再执行一个写操作，最后发起明确的新只读查询；新进程的写请求编号为 2。初态失败不继续写入；未知写入不再次补做。

实验参数必须显式指定 B 的真实 flightId；baseline 同时指定 source/destination。B 负责每例启动前重启完整服务端复位，C 没有增加 RESET 线上操作。reply_loss_* 依赖 A 在服务端丢弃目标回复；客户端不能把自身“首次请求丢失”伪装成“首次回复丢失”。

本地 JSON Lines 日志记录请求身份、模式、目标端点、尝试次数、发送/丢弃/超时、匹配回复及实际字段、callback 序号和监控阶段。cacheHit、businessExecuted 属于服务端事实，C 日志不推断这些字段。

复核后，REQUEST_CREATED 额外记录输入参数、实际编码十六进制与超时/尝试配置，CASE_START 记录实验参数。baseline 中途业务错误/未知时停止后续写操作，仍采集终态，并保留失败/未知状态。

## 5. 已执行验证

| 类别 | 实际结果 | 验证边界 |
|---|---|---|
| 规范 8 个固定报文向量 | 通过 | Python 与文档预期逐字节一致/正确解码 |
| 六请求布局与全部成功/错误体 | 通过 | 使用独立期望报文，不只自编码自解码 |
| 畸形报文 | 通过 | 各截短长度、额外尾字节、非法 UTF-8、头字段/数值越界等 |
| 重传与匹配 | 通过 | 同字节、有限尝试、完整身份过滤、迟到包、ID 上限 |
| 首次/全部请求丢失及全部回复丢失 | 通过客户端测试 | 使用测试故障对象；不证明 Java 业务次数 |
| 监控 | 通过 | 确认前暂存、序号过滤、延迟展示、重复确认与到期 |
| 真实本机 UDP | 通过 | 六操作、固定源端口、重传、callback、2048 字节超限报文完整接收后拒绝 |
| 菜单/CLI/实验 | 通过 | 六操作输入、错误与未知、退出清理、写入故障选择器、前后查询、日志 |
| Java 互操作、三机演示 | 未执行 | 当前 A/B 核心仍为占位方法 |

测试命令：python -m unittest discover -s client/tests -v。首次 51 项通过的输出保留于 evidence/c/2026-10-07-client-unittest.txt；二次复核新增 12 项，共 63 项通过，输出保存于 evidence/c/2026-10-07-client-audit-unittest.txt。新增验证包含发送超时、baseline 异常终态、参数取证、ALO 六操作回环、确认重放及两个真实 UDP 客户端的会话/端口隔离。实际解释器 Python 3.13.3；另通过 Python 3.10 grammar 解析，尚未声称在 3.10 解释器运行过。

Python 生成的六条完整请求见 evidence/c/python-request-vectors.json，可由 python -m client.tests.export_vectors 重现。此文件是 C 编码输出，尚未被 A 的真实 Java codec 验收。

## 6. 后续联合验收

A 提供可运行通信层、双向 codec 输出、回复丢失/全丢注入及执行日志；B 提供种子数据、完成业务/监控并组织复位。随后 C 配合完成六业务、AMO/ALO、监控重放、双监控与隔离、三机验证，并将实际结果补入本章和 client/TODO.md。

不能根据本机测试应答器的固定回复写出“Java 订座已扣一次”或“三机已通过”。报告最终结论必须对应真实服务端与各成员证据。
