"""检索与重排的异常。"""


class RagError(RuntimeError):
    """检索链路错误的基类。"""


class RagConfigurationError(RagError):
    """缺少 embedding / rerank 配置。"""


class EmbeddingError(RagError):
    """向量接口调用或返回结果异常。"""


class RerankError(RagError):
    """重排接口调用或返回结果异常。"""
