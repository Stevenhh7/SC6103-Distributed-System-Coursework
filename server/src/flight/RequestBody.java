package flight;

/** [A-01] 六项请求体的封闭集合；线上不发送类型名。 */
public sealed interface RequestBody permits RouteQuery, FlightQuery, Reservation,
        MonitorRegistration, SetAirfare, IncreaseAirfare {
}
