# 服务端待办追踪

更新时间：2026-10-07。B为本任务用户，正式姓名待填；A/C由队友负责。B统一编辑本表，A提供自己的状态与证据。实现/独立验收与真实网络联合验收分开，编译不能代表功能完成。

## 已有框架

| ID | 状态 | 内容 |
|---|---|---|
| A-00 | 框架已交付 | Java17目标构建、CLI/装配、VS Code源码目录 |
| A-01 | 结构已交付 | 公共类型、枚举/常量、A/B接口、不可变快照 |

## A：协议、网络与调用语义

| ID | 基线状态 | 文件/职责 | 交付要求 |
|---|---|---|---|
| A-02 | 待实现 | BinaryProtocolCodec | 七个入口、规范/C向量互操作 |
| A-03 | 待实现 | UdpTransport/UdpServer/RequestDispatcher | IPv4收发、周期清理、校验/业务/缓存/发送顺序 |
| A-04 | 待实现 | InMemoryRequestHistory、分派器 | AMO字节/peer冲突、成功/业务错误缓存、命中不执行业务 |
| A-05 | 待实现 | LossSimulator、发送路径 | 缓存后丢指定首次回复，不跳过callback |
| A-06 | 待实现 | 服务端日志/语义证据 | 真实businessExecutions/cacheHit/DROP，交B汇总 |

B未修改A的生产源码、build.ps1或公开协议类型，不代替A实现网络层。

## B：数据、业务与回调

| ID | 实现与独立验收 | 文件/职责 | 真实联合验收 |
|---|---|---|---|
| B-01 | 已实现/通过 | SeedData、包内FlightValidation；6班/唯一ID/日期/UTF-8/票价/余座/序号 | 数据已发布，启动集成待A |
| B-02 | 已实现/通过 | handle/queryRoute/queryFlight；全部匹配/排序/详情/错误 | 待A/C |
| B-03 | 已实现/通过 | reserveSeats；校验后扣座/序号/事件；失败无副作用 | callback实际送达待A/C |
| B-04 | 已实现/通过 | setAirfare/increaseAirfare；binary32边界、幂等/非幂等效果 | 网络语义待A/C |
| B-05 | 已实现/通过 | register/eventsFor/purgeExpired/isActive/remainingMillis | 空闲循环、发送前复查/AMO重放待A |
| B-06 | 独立测试/章节/实验工具已交付 | 34业务+15监控测试；用例/runner/全丢代理/报告草稿 | 网络/三机待全组 |

## 接口交接

- [x] 现有UdpServer装配共享同一监控实例（源码核对，未运行网络）。
- [x] B业务错误返回Response，无callback/登记键/状态副作用。
- [x] 旧/过期/替换登记剩余0，只读查询不延长期限。
- [x] 事件保留监控登记身份/peer，不同session共存、航班隔离。
- [x] 序号上限拒绝修改；票价负零规范、溢出/舍入无增长拒绝。
- [ ] A首次/重放监控确认发送前刷新原登记剩余时间，不重注册。
- [ ] A缓存后发送/丢弃；AMO命中不生成事件；同键异字节/peer拒绝。
- [ ] A回复失败仍尝试有效callback，单接收者失败不影响其他人。
- [ ] A空闲最多250ms维护清理，发送前isActive。
- [ ] Java/Python真实六业务、两种语义、双监控、三台电脑完成。

## 实际验证记录

| 日期 | 范围 | 结果 | 证据 |
|---|---|---|---|
| 2026-10-07 | B业务/数据 | 34通过、0失败 | evidence/b/2026-10-07-b-self-tests.txt |
| 2026-10-07 | B监控 | 15通过、0失败 | 同上 |
| 2026-10-07 | B全丢代理本机UDP | 5通过；仅工具测试 | evidence/b/2026-10-07-loss-proxy-tests.txt |
| 2026-10-07 | Java17目标编译/装配 | 见实际输出，非网络验收 | evidence/b/compatibility.txt |
| 2026-10-07 | runner解析/DryRun/占位保护 | 见实际输出；未启动实验 | evidence/b/runner-checks.txt |
| 待联调 | Java/Python、ALO/AMO、callback | 未执行 | experiments/results.csv |
| 待演练 | 三台电脑 | 未执行 | experiments/demo_steps.md |

实际JDK25.0.4、javac --release17；JDK17运行环境待复核。详见[B_HANDOFF.md](B_HANDOFF.md)。不要用预期数字代填观察值。
