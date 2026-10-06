package flight;

import java.net.InetSocketAddress;

/**
 * [A-01/B-01] A 传给 B 的上下文；peer 来自 UDP 包，nowNanos 是服务端本机单调时间。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record RequestContext(InetSocketAddress peer, long nowNanos) {
}
