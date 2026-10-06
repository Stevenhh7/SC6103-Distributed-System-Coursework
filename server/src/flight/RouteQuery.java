package flight;

/**
 * [A-01/B-01] 操作 1 请求：两个长度前缀 UTF-8 字符串，长度按字节计算。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record RouteQuery(String source, String destination) implements RequestBody {
}
