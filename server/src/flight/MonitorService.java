package flight;

/** [B-05] A 可调用的监控视图；创建/替换登记只能从业务入口发生。 */
public interface MonitorService {
    /** 删除已过期记录；A 在正常循环及接收超时后调用。 */
    void purgeExpired(long nowNanos);
    /** callback 真正发送前再次检查原登记身份及截止时间。 */
    boolean isActive(RegistrationKey key, long nowNanos);
    /** 只读剩余毫秒；过期/不存在/已被替换都返回 0，不得续期。 */
    int remainingMillis(RegistrationKey key, long nowNanos);
}
