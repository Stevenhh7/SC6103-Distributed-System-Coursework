package flight;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/** TODO(A-04)：实现内存历史；成功和业务失败均缓存，重复请求不再调用 B。 */
public final class InMemoryRequestHistory implements RequestHistory {
    private final Map<RequestKey, HistoryEntry> entries = new HashMap<>();

    @Override
    public Optional<HistoryEntry> find(RequestKey key) {
        throw new UnsupportedOperationException("[A-04] history lookup is not implemented");
    }

    @Override
    public void saveNew(RequestKey key, HistoryEntry entry) {
        // TODO(A-04)：拒绝覆盖；HistoryEntry 已对输入/输出字节数组做防御性复制。
        throw new UnsupportedOperationException("[A-04] history storage is not implemented");
    }
}
