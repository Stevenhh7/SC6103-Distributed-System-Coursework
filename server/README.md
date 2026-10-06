# Java 服务端框架

负责人：A（协议/网络/去重）与 B（业务/监控）。基线 Java 17，仅使用 JDK。接口及消息布局以根目录 [接口与数据类型规范](../SC6103_接口与数据类型规范.md) 为准。

当前可用：公开数据类型、协议枚举/常量、A/B 接口、组件装配、启动参数和构建脚本。实际 UDP、codec、历史操作、六业务和回调暂未实现；占位方法抛出带任务编号的 `UnsupportedOperationException`，不会返回虚假成功值。

## 目录与模块

```text
server/
  README.md
  TODO.md
  build.ps1
  src/flight/       全部源码使用 package flight
  build/classes/   本地编译生成，Git 忽略
```

| 文件/分组 | 主负责人 | 作用 |
|---|---|---|
| `ServerMain.java`、`ServerConfig.java` | A | CLI、帮助与框架检查 |
| `UdpServer.java` | A | 单线程接收/清理/分派循环占位 |
| `UdpTransport.java`、`ReceivedDatagram.java` | A | UDP 边界、有效数据与源端点 |
| `RequestDispatcher.java` | A | 模式检查、去重、业务、缓存、回复与事件的总处理顺序 |
| `ProtocolCodec.java`、`BinaryProtocolCodec.java`、`ProtocolException.java` | A | 既定接口与手工编解码实现位置 |
| `RequestHistory.java`、`InMemoryRequestHistory.java`、`HistoryEntry.java` | A | 请求历史接口、待实现缓存、不可变历史快照 |
| `LossSimulator.java` | A | 缓存完成后的丢回复注入 |
| `FlightService.java`、`DefaultFlightService.java` | B | 业务入口、六操作的占位函数 |
| `MonitorService.java`、`InMemoryMonitorService.java`、`Subscription.java` | B | 登记、剩余时间、过期和事件生成 |
| `Flight.java`、`FlightTime.java`、`SeedData.java` | B | 数据模型及待实现初始化 |
| `ProtocolConstants.java`、四个协议枚举 | A，与 C 对照 | 显式线协议值，不使用 ordinal |
| 其余 Request/Reply/Body/Result/Callback 等 record | A/B 共用 | 一份公共结构，严格对照规范第 7 节 |

public 类型各自一个 Java 文件是当前规范的约定，因此 DTO 文件较多。A/B 不要另建第二套字段相似但含义不同的 Request/Response。

## VS Code 打开方式

在 VS Code 中打开**整个仓库根目录**（同时包含 `client/`、`server/` 和 `.vscode/`）。根目录的 `.vscode/settings.json` 已将 Java 源码根目录指定为 `server/src`，因此 `server/src/flight/ServerMain.java` 对应的包声明就是 `package flight;`。

VS Code 自动编译结果存入 `server/build/vscode/`；下面的构建脚本仍输出到 `server/build/classes/`。两处都由 Git 忽略。

如果更新配置后包声明仍报红，按 `Ctrl+Shift+P` 执行 `Java: Clean Java Language Server Workspace`，按提示重新启动 Java 语言服务并等待索引完成。命令行构建可以独立验证 Java 源码是否通过编译。

## Windows 构建与检查

在**仓库根目录**执行：

```powershell
.\server\build.ps1
java -cp server/build/classes flight.ServerMain --help
java -cp server/build/classes flight.ServerMain --check
java -cp server/build/classes flight.ServerMain --bind 127.0.0.1 --port 6789 --semantics amo --check
```

脚本使用 `javac --release 17 -encoding UTF-8`，支持当前含空格的仓库路径，不下载依赖。重新修改 Java 文件后需要重新构建。

macOS/Linux 可在 server 目录执行等价构建：

```sh
mkdir -p build/classes
find src -name '*.java' -print > build/sources.txt
javac --release 17 -encoding UTF-8 -d build/classes @build/sources.txt
java -cp build/classes flight.ServerMain --check
```

`--check` 只构造依赖，确认 A/B 引用一致；不调用 SeedData、不绑定端口。普通启动目前报告 A-03 未实现并以退出码 2 结束。退出码 0 不代表服务端已运行或通过网络测试。

## 参数与共享边界

| 参数 | 默认/格式 | 当前状态 |
|---|---|---|
| `--bind` | `0.0.0.0` | 已解析；实际绑定待 A-03 |
| `--port` | `6789` | 范围校验已实现 |
| `--semantics` | `amo` 或 `alo` | 已解析；语义分支待 A-04 |
| `--drop-first-reply` | `UUID:requestId` | 已解析；注入待 A-05 |
| `--check` | 开关 | 装配检查，不访问网络 |

`UdpServer` 已建立一个 `InMemoryMonitorService`，同时传给业务与请求分派器。请保持这个共享实例：B 创建登记，A 用同一张表检查到期并计算监控重放剩余时间。

A 不修改航班/订阅容器，B 不发送网络报文。业务结果通过 `ServiceResult` 返回；只有实际执行成功的订座才生成事件。AMO 缓存命中不再调用 `FlightService.handle`，仅监控成功确认允许只读刷新 remainingMillis。

待办、先后依赖和验收条件见 [TODO.md](TODO.md)。目前已经提供集合/字节数组的防御性快照；参数和状态的完整校验仍属于 A-02/B-01 至 B-05。
