# Python 客户端框架

主负责人：C。运行基线：Python 3.10+，仅使用标准库。字段和消息格式以根目录 [接口与数据类型规范](../SC6103_接口与数据类型规范.md) 为准。

当前可用：数据类型、协议枚举/常量、启动参数、模块装配和框架检查。编解码、UDP、重传、菜单和回调尚未实现，调用占位函数会抛出带待办编号的 `NotImplementedError`。当前不是可连接服务器的完整客户端。

## 目录与职责

| 文件 | 内容 | 跟踪任务 |
|---|---|---|
| `__main__.py`、`client.py` | 模块入口、参数解析、待实现的六操作菜单 | C-00、C-06 |
| `config.py` | 启动配置、故障选择器解析 | C-00 |
| `protocol.py` | 固定线协议常量、消息类型、操作码、错误码 | C-01 |
| `models.py` | 请求、回复、callback、调用结果等不可变 DTO | C-01 |
| `protocol_codec.py` | 两个公共编解码入口及 ProtocolError | C-02 |
| `udp_transport.py` | 保持同一 socket 的传输接口 | C-03 |
| `invoker.py` | 会话/编号、超时重传、回复匹配的入口 | C-04 |
| `monitor.py` | callback 分流和到期等待入口 | C-05 |
| `loss_simulator.py` | 客户端首次请求丢失注入 | C-07 |
| `experiments.py` | 复用 Invoker 的实验入口 | C-08 |
| `TODO.md` | 完成状态、依赖、交接和验收事项 | 持续更新 |

公共消息 DTO 保持规范中的 camelCase 字段名，例如 `flightId`、`requestId`；仅 Python 本地配置与调用上下文使用规范约定的 snake_case。不要在未同步两端时改名或改变字段顺序。

## 当前可运行的检查

在**仓库根目录**执行：

```text
python -m client --help
python -m client --check
python -m client --server 127.0.0.1 --port 6789 --semantics amo --check
python -m compileall -q client
```

`--check` 只验证配置、模块导入和依赖装配，不创建 socket、不发送数据。运行入口固定用 `python -m client`，不要直接执行 `python client/client.py`，以保证相对导入正常。

普通启动（不带 `--check`）目前显示 C-06 未实现并以退出码 2 结束。退出码 0 仅代表帮助/框架检查成功，不表示已经通过业务验收。

## 启动参数

| 参数 | 默认值/格式 | 备注 |
|---|---|---|
| `--server` | `127.0.0.1` | 跨电脑时填 Java 服务端实际 IPv4 地址 |
| `--port` | `6789` | UDP 端口，1..65535 |
| `--semantics` | `amo`，也支持 `alo` | 将来编码到头部并由服务端检查 |
| `--timeout-ms` | `1000` | 毫秒；每次尝试用绝对截止时间 |
| `--max-attempts` | `5` | 包含首次发送，不是额外重传次数 |
| `--session-id` | 随机 UUID v4 | 可在实验中指定非零 UUID |
| `--drop-first-request` | `UUID:requestId` | 参数解析已接入，实际丢弃逻辑 C-07 待实现 |
| `--check` | 开关 | 不建立网络连接的框架装配检查 |

## 接手顺序

1. C 与 A 对照规范第 10 节，分别实现 codec，互读对方产生的完整消息。
2. 实现 UdpTransport，保持一个本地 socket；先打通查询，再加菜单和重传。
3. 实现 Invoker 的请求身份、错误/成功匹配、未知结果与 callback 暂存。
4. 接入监控倒计时和请求丢失，最后完善实验入口与真实网络验证。

所有待办及完成判据在 [TODO.md](TODO.md)。完成一项后同时更新任务状态、验证命令和证据位置；不要仅删除 TODO 注释而没有验收记录。
