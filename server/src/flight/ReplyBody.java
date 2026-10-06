package flight;

/** [A-01] 由 operation/status 决定具体类型；错误体不能按成功体解析。 */
public sealed interface ReplyBody permits RouteResult, FlightDetails, ReservationResult,
        MonitorResult, FareResult, ErrorBody {
}
