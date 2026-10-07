# 客户端需求复核记录

日期：2026-10-07。核查范围：C 客户端代码、测试、实验入口、证据与交接文档。结果：发现并修复 3 类遗漏；补充 12 项测试，总计 63 项。完整 Java/三机联合验收继续保留待完成状态。

## 依据与冲突处理

1. SC6103_接口与数据类型规范.md v1.0：线上字段、数据范围、接收匹配、监控剩余时间和公开接口的依据。
2. SC6103_三人详细分工与接口责任表.md：C-02～C-09 及文件归属的最新依据。
3. SC6103_项目指南与三人分工.md：课程目标、实验和演示要求；与上述新文档冲突的旧协议/分工描述不采用。
4. client/TODO.md：将实际实现与待联合验收区分记录，逐项核查是否有对应代码和测试。

采用 32 字节头、remainingMillis 毫秒、登记请求身份作为 callback 身份；实验组织和全组报告由 B 汇总。GUI 不属于必做项，本次不新增界面需求。

## 已复现并修复的遗漏

| 编号 | 触发与影响 | 修复 | 回归验证 |
|---|---|---|---|
| R1 / C-03、C-04 | receive 将 socket 超时缩到剩余时间后，send 沿用旧值；首次发送还可能无限阻塞。sendto 超时会直接抛出，跳过有限尝试/结果未知流程 | 每次 send 重设有限上限；Invoker 将发送超时计入本次尝试，继续等待该尝试剩余时间，用原 ID/字节重试；耗尽返回未知 | 发送继承 0.5ms 超时、提前发送超时、连续发送超时三项回归 |
| R2 / C-08 | baseline 中途订座等写操作未确认时直接退出，未采集终态；与客户端说明中“未知后只查询终态”的承诺不符 | 停止后续写操作，统一执行新的只读终态查询；即使查询成功，也保持原写操作未知/错误及实验失败状态 | baseline 订座未知后的实际调用序列为详情→路线→订座→详情；不继续设置/增加票价 |
| R3 / C-08、C-09 | 日志有操作码和响应，但缺输入数量/价格/监控时长及超时配置，单靠日志不能完整重现实验 | REQUEST_CREATED 保存请求参数、完整编码十六进制、timeoutMs/maxAttempts；CASE_START 保存实验参数，初态失败也写 CASE_END | 请求与实验参数日志可解析且内容与实际调用一致 |

R3 是实验取证补全，不是线协议修改。REQUEST_CREATED.body 是调用输入，encodedHex 是实际发送字节；浮点线上值以 encodedHex 中的 binary32 为准。所有新增内容只在本地日志。

修复前新增 11 项核查测试中，6 项暴露上述问题，5 项通过；修复后这 11 项均通过。另补 ALO 模式六操作真实回环 UDP，共新增 12 项。没有用模拟成功响应代替生产返回值。

## 逐项覆盖表

| 要求 | 代码/验证位置 | 本次结论 |
|---|---|---|
| 六操作及退出、输入错误不崩溃 | client.py、input_validation.py；test_client | 已覆盖菜单与错误/未知显示 |
| 32 字节头、UUID 原始字节、大端整数、binary32 | protocol_codec.py；test_protocol_codec | 已覆盖规范向量及六请求布局 |
| UTF-8 字节长度、数值/日期/长度/尾字节校验 | protocol_codec.py；test_protocol_codec | 已覆盖中文、边界与畸形消息 |
| 错误先按 status 解析；未知 op 只允许错误体 | decode_message；test_protocol_codec | 已覆盖 |
| IPv4、固定解析端点、实际来源、65535 缓冲 | udp_transport.py；test_udp_transport | 真实本机 UDP 通过，超限包完整接收后拒绝 |
| 新调用新 ID、重传同 ID/字节/端口、编号不回绕 | invoker.py；test_invoker、test_udp_transport | 已覆盖 |
| 绝对截止、无关包和 callback 不延时 | invoker.py；test_invoker | 已覆盖；新增发送超时的有界处理 |
| 成功/业务错误终止；耗尽未知不补做写操作 | invoker.py；test_invoker、test_requirements_audit | 已覆盖接收全丢与发送超时 |
| ALO/AMO 头与模式不匹配错误回显 | test_requirements_audit、test_udp_transport | 两种模式六操作回环通过；不代表服务端两种执行语义已验收 |
| callback 来源/会话/登记/航班/mode、递增序号 | monitor.py；test_monitor、test_invoker | 已覆盖旧身份/乱序/重复/异航班 |
| 确认前暂存最高序号，失败清空 | invoker.py；test_invoker | 已覆盖 |
| 确认接收时刻+剩余毫秒、0 立即结束、不续期 | monitor.py；test_monitor、test_requirements_audit | 新增重传后缩短确认及过期重放组合验证 |
| 两个独立客户端可用、相同 requestId 不混淆 | test_requirements_audit | 两个并发真实 UDP socket，独立 UUID/端口；交叉身份 callback 被过滤 |
| 指定 RequestKey 首次请求丢弃且计入尝试 | loss_simulator.py；test_invoker、test_experiments | 已覆盖 |
| 实验复用 Invoker，输出前后状态与真实参数 | experiments.py；test_experiments、test_requirements_audit | 已覆盖；baseline 异常终态遗漏已修复 |
| 全部请求丢失与全部回复丢失分别验证 | test_invoker | 客户端独立故障测试已覆盖；真实 Java 状态/次数待联调 |
| 正常/EOF/Ctrl+C/网络异常关闭 socket | client.py；test_client、test_udp_transport | 已覆盖 |
| 报告、向量、运行说明与待办 | README、HANDOFF、TODO、report/C_客户端与跨语言.md、evidence/c | 已同步本次结果 |

## 尚未验收、不能由 C 单方面补齐的事项

- A 的真实 Java codec 双向互操作：C 已导出六条完整请求，等待 Java 解码结果和 Java 生成回复。
- A/B 的真实六业务、ALO/AMO 执行次数、缓存命中、首次/全部回复丢失后的业务状态。
- B 的登记替换/到期与 A 的动态剩余时间重放。客户端已通过模拟重放序列，服务端真实计时尚待验证。
- 真实服务端下双监控、航班隔离、回复丢失仍回调，以及三台电脑局域网演示。
- B 发布种子清单、实验结果表和演示步骤，并同步其负责的根 README/旧分工描述。

当前 A/B 核心仍包含占位方法，因此这些项目继续列为待联调，不写成客户端代码已保证的业务结论。

## 复现命令与证据

~~~text
python -m unittest discover -s client/tests -v
python -m unittest client.tests.test_requirements_audit -v
python -m client --check
~~~

最终完整输出：[复核测试记录](../evidence/c/2026-10-07-client-audit-unittest.txt)。首次实现的 51 项记录仍保留，不覆盖历史证据。实际解释器 Python 3.13.3；Python 3.10 grammar 检查不等同于在 3.10 解释器执行。
