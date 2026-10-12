package flight;

import java.util.Optional;

/** [A-05] 仅作用于普通回复；调用位置必须在实际业务与历史写入之后。 */
public final class LossSimulator {
    private final Optional<RequestKey> target;
    private boolean dropped;

    public LossSimulator(Optional<RequestKey> target) {
        this.target = java.util.Objects.requireNonNull(target);
    }

    /** [A-05]：只丢目标键的首次回复，缓存重放的后续发送也经过此入口。 */
    public boolean shouldDropReply(RequestKey key) {
        if (!dropped && target.filter(key::equals).isPresent()) {
            dropped = true;
            return true;
        }
        return false;
    }
}
