# SC6103-Distributed-System-Coursework
SC6103 小组作业：Java 17 服务端 + Python 3.10+ 客户端，UDP 航班信息系统。

当前阶段为**可编译/可导入的代码框架**。消息类型、接口、模块和启动配置已建立；具体编解码、UDP 通信、业务、调用语义与回调由小组后续实现。占位函数会明确报未实现，不返回虚假的业务成功。

## 代码目录与分工

| 目录 | 负责人 | 说明 |
|---|---|---|
| [client](client/README.md) | C | Python 客户端、调用/监控/实验入口；[待办追踪](client/TODO.md) |
| [server](server/README.md) | A/B | A 负责 Java 协议/网络/去重，B 负责业务/监控；[待办追踪](server/TODO.md) |

实际目录采用 `client/` 与 `server/`；原指南中的 `client-python/`、`server-java/` 目录草案由这两个目录替代。接口仍严格依据规范 v1.0。

## 框架检查

使用 VS Code 时，请打开整个仓库根目录；`.vscode/settings.json` 已配置 Java 源码目录为 `server/src`。包声明报红的重新加载步骤见 [服务端说明](server/README.md#vs-code-打开方式)。

在仓库根目录的 PowerShell 中运行，无需安装第三方依赖：

```powershell
python -m client --help
python -m client --check
.\server\build.ps1
java -cp server/build/classes flight.ServerMain --help
java -cp server/build/classes flight.ServerMain --check
```

`--check` 只检查配置、类型导入和模块装配，不打开 socket。普通启动当前以退出码 2 提示尚未实现；完成各目录 TODO 后再进行真实查询、订座和回调验证。

## 协作约定

- 代码注释中的任务编号与各目录 TODO 对应，完成后补真实验证记录。
- 每人负责自己模块的测试和报告；C 负责集成和汇总。
- A/C 共享一份二进制规范，各自实现 codec；B 通过公共 Java 类型接入。
- 协议变更先改规范并同步两端；实验结果不得用文档预期值代填。
- `server/build/` 和 Python 缓存属于本地产物，已加入 Git 忽略。

## 项目文档

- [项目指南与三人分工](SC6103_项目指南与三人分工.md)：任务范围、成员职责、实验及排期。
- [接口与数据类型规范 v1.0](SC6103_接口与数据类型规范.md)：Java/Python 共用的报文、数据类型和模块接口；接口实现以此为准。
