> **2026-10-10 集成更新：** A 已实现；Java 17 下 200 组测试及 16 项真实本机 UDP 实验通过，R2 监控提前结束误判已修复。三机演示仍待执行。A Zhang Zhiyin / B Peng Jinyu / C Ji Chengyu。下方保留原日期的设计/交接/待办记录，旧“未实现/待联调”状态已被本更新取代；协议 v1.0 字段不变。当前状态见 [A 交接](../server/A_HANDOFF.md) 和 [验证证据](../evidence/a/README.md)。

# C 客户端交接记录

日期：2026-10-07。任务：C-02～C-08 实现与 C-09 独立测试。成员姓名待填写。

## 交付

- C 所有生产占位函数已实现，保留 encode_request、decode_message、Invoker.invoke、monitor_until_expiry、run_case 的原签名。
- 协议 v1 字段、操作码、错误码、CallOutcome 和 AcceptedMonitor 均保持不变。
- 新增本地 ExperimentConfig、输入/展示/日志辅助模块及测试，不改变线上协议。
- 新增 --case、--flight-id、实验数值参数、--log-file、--verbose；全部使用现有 Invoker。
- 63 项独立测试通过；包括模拟时间和真实本机 UDP。实际运行 Python 3.13.3；3.10 语法检查通过。
- 实现说明见 README；原始测试输出及 Python 请求向量见 evidence/c；C 报告章节见 report。
- 二次复核修复发送超时处理、baseline 中途失败后的终态查询，补全参数日志；详见 [AUDIT.md](AUDIT.md)。

## 给 A 的对接项

1. 读取 evidence/c/python-request-vectors.json，用 Java decodeRequest 解出六请求；请回传 Java 编码的成功/错误/callback 全报文字节。
2. C 已验证 status=7 且 semantics 回显请求模式的错误回复能结束调用。
3. 故障用例固定 UUID 时目标写请求为 UUID:2（ID=1 是初态查询）。A 的 --drop-first-reply 应选择 2。
4. 全回复丢失需测试注入选择写请求，初态/终态查询正常放行；callback 不受丢包开关影响。
5. C 日志不猜测实际执行次数/cacheHit；请由 A 提供相同 session/requestId 的服务端证据。

## 给 B 的对接项

1. 提供 SeedData 对应的 ID/路线/初始余座/票价；C 的 --flight-id 必须显式指定，无固定种子假设。
2. 独立用例由 B 重启整个服务端复位；客户端无 RESET 操作。
3. baseline 只执行一名客户端的六操作。双监控由两个独立 monitor 进程接收，另一个订座调用触发更新；先确认登记再订座。
4. C 根据成功确认中的 remainingMillis 建立截止时间，不按原始 durationSeconds 重新等待。待联调 B 的到期/替换与 A 的重放。
5. 请将根 README 和旧指南中的“客户端仍为框架”“C 汇总全组报告”改为当前实现状态和最新分工；本次保留 B 负责文件供其统一更新。

## 可复现验证

~~~text
python -m unittest discover -s client/tests -v
python -m client --check
python -m client.tests.export_vectors
~~~

当前 Java 核心仍抛 UnsupportedOperationException，故未记录任何“真实 Java 业务通过”或“三台电脑通过”的结论。C-09 的联调部分保持待完成。
