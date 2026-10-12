package flight;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/** [A-04] 内存历史；成功和业务失败均缓存，重复请求不再调用 B。 */
public final class InMemoryRequestHistory implements RequestHistory {
    private final Map<RequestKey, HistoryEntry> entries = new HashMap<>();

    @Override
    public Optional<HistoryEntry> find(RequestKey key) {
        return Optional.ofNullable(entries.get(java.util.Objects.requireNonNull(key)));
    }

    @Override
    public void saveNew(RequestKey key, HistoryEntry entry) {
        // [A-04]：拒绝覆盖；HistoryEntry 已对输入/输出字节数组做防御性复制。
        java.util.Objects.requireNonNull(key);
        java.util.Objects.requireNonNull(entry);
        if (entries.putIfAbsent(key, entry) != null) {
            throw new IllegalArgumentException("Request history cannot be overwritten");
        }
    }
}
