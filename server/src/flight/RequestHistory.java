package flight;

import java.util.Optional;

/** [A-04] 请求历史接口；生命周期为整个服务端进程，不随短超时清空。 */
public interface RequestHistory {
    /** 查找原请求、源端点和结果快照；冲突判断由 RequestDispatcher 完成。 */
    Optional<HistoryEntry> find(RequestKey key);

    /** 只写新键，不覆盖已有结果；必须在发送或模拟丢回复之前写入。 */
    void saveNew(RequestKey key, HistoryEntry entry);
}
