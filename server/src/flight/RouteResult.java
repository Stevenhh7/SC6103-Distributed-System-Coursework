package flight;

import java.util.List;

/**
 * [A-01/B-01] 操作 1 成功体；count 由列表大小导出，结果按 ID 升序。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record RouteResult(List<Integer> flightIds) implements ReplyBody {
    public RouteResult {
        flightIds = List.copyOf(flightIds);
    }
}
