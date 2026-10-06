package flight;

import java.util.Map;

/** [B-01] 固定演示数据入口；不要把空 Map 当作已经完成的初始化。 */
public final class SeedData {
    private SeedData() {}

    /**
     * TODO(B-01)：返回已验证、ID 唯一的最多 100 班数据。
     * 覆盖同路线多班、零余座、中文地点；订座实验包含初始余座 10 的航班。
     * 原价 100 的测试航班用于 SET 120 / INCREASE 20 对比。
     */
    public static Map<Integer, Flight> createFlights() {
        throw new UnsupportedOperationException("[B-01] seed data is not implemented");
    }
}
