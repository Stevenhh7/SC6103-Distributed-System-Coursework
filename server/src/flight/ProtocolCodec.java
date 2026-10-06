package flight;

/** [A-02] 按规范第 7.2 节固定的接口；实现放在 BinaryProtocolCodec。 */
public interface ProtocolCodec {
    /** 只检查头部和总长；不读取业务体或改变状态。 */
    Header decodeHeader(byte[] data, int offset, int length) throws ProtocolException;
    /** 解码六项请求的结构；quantity 等业务范围仍由 B 校验。 */
    Request decodeRequest(byte[] data, int offset, int length) throws ProtocolException;
    /** 编码完整请求，bodyLength 必须与实际体一致。 */
    byte[] encodeRequest(Request request) throws ProtocolException;
    /** 从原请求回显身份和模式，状态取 Response，长度由 codec 计算。 */
    byte[] encodeReply(Header requestHeader, Response response) throws ProtocolException;
    /** 按 status 先区分错误体/成功体，不能把错误说明解成航班数据。 */
    Reply decodeReply(byte[] data, int offset, int length) throws ProtocolException;
    /** 使用接收者登记身份，固定 type=3/op=4/bodyLength=12。 */
    byte[] encodeCallback(CallbackEvent event, Semantics mode) throws ProtocolException;
    /** 解码完整 callback；返回对象不表示接收者或登记已经验证。 */
    CallbackMessage decodeCallback(byte[] data, int offset, int length) throws ProtocolException;
}
