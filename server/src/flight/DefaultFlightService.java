package flight;

import java.util.LinkedHashMap;
import java.util.Map;

/** B 的业务骨架。A 只调用 handle；六操作实现分别追踪 B-02 至 B-05。 */
public final class DefaultFlightService implements FlightService {
    private final Map<Integer, Flight> flights = new LinkedHashMap<>();
    private final InMemoryMonitorService monitors;

    public DefaultFlightService(InMemoryMonitorService monitors) {
        this.monitors = monitors;
    }

    /** [B-01] 仅在启动/实验复位时调用；先成功生成数据再替换现有内容。 */
    public void loadSeedData() {
        Map<Integer, Flight> initial = SeedData.createFlights();
        flights.clear();
        flights.putAll(initial);
    }

    @Override
    public ServiceResult handle(Request request, RequestContext context) {
        // TODO(B-02)：按 operation 分派以下函数；正常错误返回 Response/ErrorBody。
        // 请求结构类型由 A 验证；B 仍须检查参数范围和状态约束，不能先修改再报错。
        throw new UnsupportedOperationException("[B-02] business dispatch is not implemented");
    }

    private ServiceResult queryRoute(RouteQuery body) {
        // TODO(B-02)：地点按规范比较，全部匹配项按 ID 升序；无匹配返回错误 1。
        throw new UnsupportedOperationException("[B-02] route query is not implemented");
    }

    private ServiceResult queryFlight(FlightQuery body) {
        // TODO(B-02)：不存在返回错误 2；详情为时间、票价、余座的快照。
        throw new UnsupportedOperationException("[B-02] flight query is not implemented");
    }

    private ServiceResult reserveSeats(Reservation body, RequestContext context) {
        // TODO(B-03)：校验 -> 扣座/序号+1 -> 结果快照及 monitors.eventsFor。
        throw new UnsupportedOperationException("[B-03] reservation is not implemented");
    }

    private ServiceResult registerMonitor(MonitorRegistration body, RequestKey key,
                                          RequestContext context) {
        // TODO(B-05)：登记后立即返回，不等待结束；ServiceResult 带 RegistrationKey。
        throw new UnsupportedOperationException("[B-05] monitor operation is not implemented");
    }

    private ServiceResult setAirfare(SetAirfare body) {
        // TODO(B-04)：有限非负 float；设置同值保持幂等，不触发座位 callback。
        throw new UnsupportedOperationException("[B-04] fare assignment is not implemented");
    }

    private ServiceResult increaseAirfare(IncreaseAirfare body) {
        // TODO(B-04)：delta 正且有限，float 结果必须有限且真正增大；失败不改价。
        throw new UnsupportedOperationException("[B-04] fare increase is not implemented");
    }
}
