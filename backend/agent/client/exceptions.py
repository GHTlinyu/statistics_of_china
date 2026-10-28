"""大模型客户端异常。"""


class LLMError(RuntimeError):
    """大模型调用相关错误的基类。"""


class LLMConfigurationError(LLMError):
    """配置缺失或非法（如缺少 LLM_API_KEY）。"""


class LLMResponseError(LLMError):
    """模型返回内容无法解析（如 JSON 模式返回非法 JSON）。"""
