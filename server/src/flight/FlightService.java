package flight;

/** [B-02] B 对 A 的唯一六操作执行入口；不得在实现内直接操作 socket。 */
public interface FlightService {
    /** 返回业务响应、待发送事件及可选监控登记身份；失败不修改状态。 */
    ServiceResult handle(Request request, RequestContext context);
}
