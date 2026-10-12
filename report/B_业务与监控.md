> **2026-10-10 集成更新：** A 已实现；Java 17 下 200 组测试及 16 项真实本机 UDP 实验通过，R2 监控提前结束误判已修复。三机演示仍待执行。A Zhang Zhiyin / B Peng Jinyu / C Ji Chengyu。下方保留原日期的设计/交接/待办记录，旧“未实现/待联调”状态已被本更新取代；协议 v1.0 字段不变。当前状态见 [A 交接](../server/A_HANDOFF.md) 和 [验证证据](../evidence/a/README.md)。

# B：航班业务与监控实现

实现/验证日期：2026-10-07。作者正式姓名待填写。依据v1.0及main `2cc2e66d69f38237653297089406ba9ad0baaaf9`，未改公共接口或消息字段。

## 数据与业务

服务端以不可变Flight保存ID、路线、UTC+8起飞时间、binary32票价、余座与更新序号，业务容器用Map按ID检索。修改时替换Flight，成功回复与事件是独立快照，后续写操作不改变先前已返回或缓存的结果。

SeedData返回6班已验证固定数据，覆盖同路线多班、零余座、中文地点；1001的10座/100SGD供语义对比。验证最多100班、唯一正ID、合法1..9999年日期、UTF-8地点最大128字节、有限非负票价、非负余座和初始序号0。非法种子在发布前抛初始化错误，不发布部分数据。

handle按照操作码分派六业务，正常业务失败使用Response/ErrorBody，失败不扣座、不改价、不登记、不增加序号、不生成事件。输入范围先检查，随后查航班，再检查状态限制。地点只去除U+0020两端空格，大小写敏感，保留其他空白和Unicode形式。

路线查询返回全部匹配ID且升序，没匹配status1；详情只返回规定时间/票价/余座；不存在航班status2。订座检查数量>0、余座足够和序号上限，成功扣座/序号+1后生成有效订阅事件。失败数量status4、座位不足status3、序号达到2147483647后status9且状态不变。

SET_AIRFARE保存有限非负float，-0规范为+0；重复赋相同值最终状态相同。INCREASE_AIRFARE必须是有限正delta，float加法结果必须有限且真正增大；溢出或舍入后无变化status4。两者不触发座位事件。直接连续执行INCREASE20会从100变120、140，体现非幂等业务效果；它不等于已经完成UDP丢包语义实验。

## 监控生命周期

register记录session、登记requestId、flightId、实际peer、原时长与服务器nanoTime到期值。同session/flight新登记替换旧登记，不同session可同时监控同航班；不同航班隔离。validate先完成，再替换，失败登记不会删除旧登记。

eventsFor对目标航班返回仍有效的CallbackEvent快照，带原登记身份、接收端点、最新余座与序号，不发送网络包。isActive随时按身份和时间判断；登记过期或被替换即false。purgeExpired负责删除失效记录，A需要在空闲循环中周期调用。

remainingMillis是只读计算：floor((expiry-now)/1e6)，下限0，上限原durationSeconds*1000；缺失/过期/替换为0。差值比较支持nanoTime负值与long跨界。距离到期少于1ms时，remainingMillis可以为0，而服务器登记在精确纳秒截止前仍活动，符合向下取整定义。

B不实现请求历史。ALO每次真实register执行会替换/延长登记；AMO缓存命中由A拦截，只读查询原登记剩余时间，不调用handle/register。A须在每次准备发送监控确认时重新计算remainingMillis，不能直接重放旧时长。

## 独立验证与实际结论

执行命令：`server/test-b.ps1 -EvidenceFile evidence/b/2026-10-07-b-self-tests.txt`。

实际结果：BusinessSelfTest **34通过、0失败**；MonitorSelfTest **15通过、0失败**。没有sleep，采用确定的时钟值和方法调用。测试反射仅用于注入序号等极端状态与确认过期项确实移除；未增加测试用公共生产接口。原始输出见evidence/b。

覆盖数据唯一/数量/日期/UTF-8边界、中文和排序、输入与状态错误、失败无副作用、快照、序号上限、票价非有限/溢出/舍入、双会话/隔离、登记替换/失败保持、无清理到期、剩余时间和nanoTime跨界。

本轮B验收工具共27项Python测试通过：证据核对17项（其中一项用C实际日志生成流程遍历16种case/mode）、运行前检查4项、代理6项。代理部分覆盖真实回环UDP目标全丢、查询/其他身份/callback放行、后端端点稳定、来源过滤，并补查日志实际身份与故障目标分开记录。其余测试采用受控传输/时钟或模拟就绪响应。它们不替代真实Java服务端，也不计入49项Java业务测试。

runner通过16次预演、当前A占位拒绝，以及隔离fixture中的端口占用和自有Java启动失败记录测试。fixture故意没有Java服务端class，没有把fixture结果写入真实results.csv。原始证据见evidence/b/2026-10-07-review-tools-tests.txt、2026-10-07-review-runner-checks.json。

环境：实际JDK25.0.4，使用javac --release17；Python实际版本见evidence/b/environment.txt。Java17运行环境的复核待其他成员/最终干净环境执行。

## 实验与集成限制

已准备seed_manifest、cases、runner、结果模板和demo_steps。每例重启服务端复位所有状态，1001固定初态，写目标session:2，记录真实查询/unknown与A执行/缓存日志。SET的终态不能单独证明去重。全请求/全回复丢失使用独立代理，不新增生产操作。

runner新增端口/就绪检查，核对每个请求的session、模式、ID、操作、输入、阶段顺序、实际响应、逐次发送与超时；全丢必须有5条目标故障记录。输出仅STATE_VERIFIED_NEEDS_A_LOG_REVIEW，仍由A审核实际业务/缓存/回复故障证据。详细协作安排见[B复查与联调计划](../experiments/B_复查与队友联调计划.md)。

基线A仍抛占位异常，因此真实Java/Python六业务、ALO/AMO网络语义、callback发送顺序、空闲250ms清理和三机演示尚未执行。不能把独立Java测试、C已交付的客户端测试或预期数字替代这些结论。B模块实现与独立验证已交付；整体项目待A实现后联调。
