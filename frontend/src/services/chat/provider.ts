/**
 * 自定义 Chat Provider：适配后端私有 SSE 协议（start / token / done / error）。
 *
 * 依据 @ant-design/x-skill 的 x-chat-provider 技能规则：
 * - 只实现 transformParams / transformLocalMessage / transformMessage 三个方法，禁止重写 request
 * - XRequest 必须配置 manual: true
 *
 * 协议说明（backend/app/schema/chatDTO.py）：
 * 后端 SSE 为 `data: {"type": ..., "data": {...}}\n\n` 帧，XRequest 默认解析器
 * （分隔符 \n\n / \n / :）恰好与之匹配，chunk 形如 { data: '<json string>' }，
 * 因此无需自定义 transformStream，在 transformMessage 里 JSON.parse 即可。
 */
import { AbstractChatProvider, XRequest } from '@ant-design/x-sdk';
import type {
  SSEOutput,
  TransformMessage,
  XRequestOptions,
} from '@ant-design/x-sdk';
import type { ChatEvent, ChatInput, ChatMessage } from './types';

/** 后端 SSE error 事件 / 非 200 响应抛出的错误，供 requestFallback 区分展示文案 */
export class ChatRequestError extends Error {
  readonly httpStatus?: number;

  constructor(message: string, httpStatus?: number) {
    super(message);
    this.name = 'ChatRequestError';
    this.httpStatus = httpStatus;
  }
}

export class BackendChatProvider extends AbstractChatProvider<
  ChatMessage,
  ChatInput,
  SSEOutput
> {
  transformParams(
    requestParams: Partial<ChatInput>,
    options: XRequestOptions<ChatInput, SSEOutput, ChatMessage>,
  ): ChatInput {
    return {
      ...(options.params || {}),
      content: requestParams.content ?? '',
    };
  }

  transformLocalMessage(requestParams: Partial<ChatInput>): ChatMessage {
    return {
      role: 'user',
      content: requestParams.content ?? '',
    };
  }

  transformMessage(
    info: TransformMessage<ChatMessage, SSEOutput>,
  ): ChatMessage {
    const { originMessage, chunk } = info;
    // onSuccess 阶段 chunk 为 undefined：保持最终内容不变
    const fallback: ChatMessage = originMessage ?? {
      role: 'assistant',
      content: '',
    };

    if (!chunk?.data) {
      return fallback;
    }

    let event: ChatEvent;
    try {
      event = JSON.parse(chunk.data);
    } catch {
      // 非 JSON 帧（如 keep-alive 注释），忽略
      return fallback;
    }

    switch (event.type) {
      case 'token':
        return {
          role: 'assistant',
          content: `${fallback.content}${event.data.content ?? ''}`,
        };
      case 'error':
        // 抛错 → 沿 XRequest onUpdate 调用链传导到 onError → useXChat 的 requestFallback
        throw new ChatRequestError(
          event.data.message || '生成失败，请稍后重试',
        );
      case 'start':
      case 'done':
      default:
        return fallback;
    }
  }
}

/** 每个会话一个独立 Provider 实例（use-x-chat 技能：多会话必须隔离状态） */
const providerCache = new Map<string, BackendChatProvider>();

function handleResponse(response: Response): Response {
  if (response.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new ChatRequestError('登录已过期，请重新登录', 401);
  }
  return response;
}

export function getChatProvider(conversationId: number): BackendChatProvider {
  const key = String(conversationId);
  const cached = providerCache.get(key);
  if (cached) {
    return cached;
  }

  const provider = new BackendChatProvider({
    request: XRequest<ChatInput, SSEOutput, ChatMessage>(
      `/api/conversation/${conversationId}/chat`,
      {
        manual: true,
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') ?? ''}`,
        },
        middlewares: {
          onResponse: async (response) => handleResponse(response),
        },
        // 相邻 token 间隔超过 2 分钟视为超时（RAG 检索 + 生成可能较慢）
        streamTimeout: 120000,
      },
    ),
  });

  providerCache.set(key, provider);
  return provider;
}

/** 删除会话时释放 Provider 缓存 */
export function removeChatProvider(conversationId: number): void {
  providerCache.delete(String(conversationId));
}
