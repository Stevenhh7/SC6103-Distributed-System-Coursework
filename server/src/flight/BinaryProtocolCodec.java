package flight;

/**
 * TODO(A-02)：实现手工 byte[] 编解码，禁止对象序列化和输入/输出流类。
 * 先实现有边界检查的 i32/u16/f32/UUID/UTF-8 辅助函数，再实现以下入口。
 * 对照规范第 10 节固定向量，不要只测试同一编码器和解码器的往返。
 */
public final class BinaryProtocolCodec implements ProtocolCodec {
    @Override
    public Header decodeHeader(byte[] data, int offset, int length) throws ProtocolException {
        throw new UnsupportedOperationException("[A-02] decodeHeader is not implemented");
    }

    @Override
    public Request decodeRequest(byte[] data, int offset, int length) throws ProtocolException {
        throw new UnsupportedOperationException("[A-02] decodeRequest is not implemented");
    }

    @Override
    public byte[] encodeRequest(Request request) throws ProtocolException {
        throw new UnsupportedOperationException("[A-02] encodeRequest is not implemented");
    }

    @Override
    public byte[] encodeReply(Header requestHeader, Response response) throws ProtocolException {
        throw new UnsupportedOperationException("[A-02] encodeReply is not implemented");
    }

    @Override
    public Reply decodeReply(byte[] data, int offset, int length) throws ProtocolException {
        throw new UnsupportedOperationException("[A-02] decodeReply is not implemented");
    }

    @Override
    public byte[] encodeCallback(CallbackEvent event, Semantics mode) throws ProtocolException {
        throw new UnsupportedOperationException("[A-02] encodeCallback is not implemented");
    }

    @Override
    public CallbackMessage decodeCallback(byte[] data, int offset, int length) throws ProtocolException {
        throw new UnsupportedOperationException("[A-02] decodeCallback is not implemented");
    }
}
