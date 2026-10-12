# Java UDP 服务端

A：Zhang Zhiyin；B：Peng Jinyu。JDK 17+，仅 JDK 标准库。A 网络/协议/语义与 B 六业务/监控均已实现，真实 Java/Python 本机 UDP 已验证。

## 构建与运行

仓库根目录执行：

```sh
python3 -c 'from experiments.run_suite import compile_java; compile_java()'
java -cp server/build/classes flight.ServerMain --bind 0.0.0.0 --port 6789 --semantics amo
```

macOS/Linux 可用 `sh server/build.sh`；Windows 可用 `server/build.ps1` 或将上例 python3 改为 python。编译使用 `javac --release 17 -encoding UTF-8`，结果在被 Git 忽略的 `server/build/classes`。

| 参数 | 默认/用途 |
|---|---|
| --bind | 0.0.0.0；IPv4 |
| --port | 6789 |
| --semantics | amo；也可 alo |
| --drop-first-reply | UUID:ID；只丢指定请求的第一次普通回复 |
| --check | 离线装配检查，不装载种子、不绑定端口 |
| --help | 参数说明 |

普通启动加载六班固定数据并输出 SERVER_READY。停止后重启恢复初态，同时清空历史/订阅。不要重用旧 session 跨重启声称 AMO 保证。

## 结构与保证

- BinaryProtocolCodec：手工大端数字与严格 UTF-8；32 字节头；应用报文最多 1024 字节。按实际接收长度解析。
- UdpTransport/UdpServer：同一个 IPv4 DatagramSocket；65535 字节接收；250ms 超时驱动空闲过期清理；单线程分派。
- RequestDispatcher：头部与模式校验、AMO 历史检查、业务、缓存、普通回复、回调。回复丢失/发送失败不会跳过回调。
- InMemoryRequestHistory：进程生命周期内保留成功和业务错误；同键异字节或异 peer 拒绝；命中不重执行业务。
- DefaultFlightService/SeedData/InMemoryMonitorService：既有 B 模块；A/B 共用唯一监控对象。
- ServerLog：JSON Lines 输出实际接收、执行、缓存、命中、丢弃与发送事件，用于交叉审计。

AMO 监控确认重放只刷新原登记 remainingMillis，不续期；过期或替换返回 0。回调使用原登记身份，发送前检查有效性，每个接收者独立处理发送失败。回调是尽力投递，无确认或重传。

## 验证与交接

`python3 -m experiments.verify_all --matrix` 执行模块、边界与真实网络验证。最终证据见 [evidence/a](../evidence/a/README.md)，设计和逐项验收见 [A_HANDOFF](A_HANDOFF.md)。

实际验证：javac 21 使用 --release 17；Temurin Java 17.0.20.1 运行；Python 3.13.1。未将 Windows 专用 PowerShell 脚本冒充已在 Windows 上运行。VS Code 请打开整个仓库；源码根为 server/src，包 flight。
