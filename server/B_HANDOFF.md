> **2026-10-10 集成更新：** A 已实现；Java 17 下 200 组测试及 16 项真实本机 UDP 实验通过，R2 监控提前结束误判已修复。三机演示仍待执行。A Zhang Zhiyin / B Peng Jinyu / C Ji Chengyu。下方保留原日期的设计/交接/待办记录，旧“未实现/待联调”状态已被本更新取代；协议 v1.0 字段不变。当前状态见 [A 交接](../server/A_HANDOFF.md) 和 [验证证据](../evidence/a/README.md)。

# B 模块交接记录

日期：2026-10-07。基线：main `2cc2e66d69f38237653297089406ba9ad0baaaf9`。负责人姓名待补。

## 已交付

- SeedData：6班固定航班，数据上限、唯一ID、UTF-8地点、日期、票价、余座及初始序号校验。
- DefaultFlightService：handle 与六业务；合法输入/状态检查完成后修改；失败返回错误，无事件。
- InMemoryMonitorService：register、eventsFor、purgeExpired、isActive、remainingMillis，原签名全部保留。
- 新增包内 FlightValidation，不改变公共DTO、接口、状态码、32字节协议。
- 34业务/数据测试 + 15监控测试通过；Java17编译目标，实际JDK25.0.4。
- B实验数据清单、用例/复位、结果模板、runner、全丢UDP代理、演示步骤、B报告章节和总稿状态表。

验证：

```powershell
.\server\test-b.ps1 -EvidenceFile evidence/b/2026-10-07-b-self-tests.txt
python -m unittest experiments.test_analyze_results experiments.test_runtime_check experiments.test_udp_loss_proxy -v
.\experiments\run_suite.ps1 -Case all_reply_loss -Semantics amo -DryRun
```

test-b.ps1 编译 production+B测试到独立目录 server/build/b-test-classes，没有改 A 的 build.ps1；测试不依赖 A codec 或 C 网络。

本轮复查：业务实现未发现需修改的缺陷，保留49项Java验证。实验工具27项测试通过（17证据核对、4运行前检查、6代理，其中1项遍历16种流程），runner的16次预演、占位拒绝、端口冲突与自有Java启动失败路径通过。增加实际报文/故障目标分离日志、身份/阶段/attempts核对、全丢证据、就绪探测及每例失败记录。原始输出见evidence/b/2026-10-07-review-tools-tests.txt和2026-10-07-review-runner-checks.json。

后续任务、三轮联调、责任归属和日程详见[B复查与队友联调计划](../experiments/B_复查与队友联调计划.md)。本轮B代码、测试和文档已纳入main，队友直接获取主分支即可；原B分支保留交付记录。D盘目录是文件镜像，联调时统一main集成版本。

现有 A 的 ServerMain --check 仍有硬编码旧提示“business 未实现”，只表示原框架说明没有更新；不能据此否定49项真实B测试，也不能据此认为服务器已监听。A完成通信层时应同步自己的启动说明。本次保留了该命令的原始输出以便审查。

## 给 A 的具体接入要求

1. 保持 UdpServer 已有的同一 InMemoryMonitorService；启动时调用 loadSeedData，RequestContext 用真实 peer 和 nanoTime。
2. FlightService.handle 每调用一次就是一次实际业务执行。B 不去重，ALO每份请求进入，AMO缓存命中由 A 在入口之前拦截。
3. 保存成功和业务错误；ServiceResult 的 response/callbacks/monitorRegistration 都按原契约返回。
4. 首次和重放监控回复均在准备发送时读取原登记 remainingMillis；不重注册，旧/过期/替换登记返回0。
5. callback 从事件的 registration 与 recipient 编码；发送前 isActive；普通回复丢失/发送失败仍尝试所有有效事件。
6. 空闲最多250ms调用 purgeExpired；isActive在到期边界直接false，不依赖已经清理。
7. 限时计算使用差值，支持 nanoTime负值/long跨界。B 不把服务器绝对时间上网发送。
8. 提供目标写请求的实际 execution/cacheHit 日志。1001初态10座/100票价；C的单写用例目标session:2。

## 给 C 的具体接入信息

1001=Singapore→Beijing，10座、100SGD；1002同路线20座；1003=Singapore→Shanghai零座；1004/1005=北京→上海。完整表见 experiments/seed_manifest.md。

C 已有 CLI 保持不变，runner 使用 --flight-id1001、quantity1、new-price120、delta20。监控用 remainingMillis；原来保存的确认快照不会随下一次业务变化。

## 仍待共同验收

A 的通信层未实现，因此真实 Java/Python互操作、网络模式缓存、空闲主循环清理、callback实际送达、三台电脑演示未执行。B的独立清理/只读重放测试不能证明A总处理顺序已经正确。results.csv保留NOT_EXECUTED；真实姓名、实际贡献比例和A章节待成员补充。
