/**
 * 会话/消息 REST 封装。
 *
 * 走 umi request（src/app.tsx 已封装：自动带 Bearer token、剥离 {code,message,data}、
 * 401 跳登录），只有 SSE 流式聊天走 XRequest。
 */
import { request } from '@umijs/max';
import type {
  ConversationDTO,
  MessageDTO,
  PageResult,
} from './types';

export const conversationApi = {
  /** 会话列表（updated_at 倒序），当前只取第一页 */
  list: () =>
    request<PageResult<ConversationDTO>>('/conversation', {
      params: { page: 1, page_size: 20 },
    }),

  /** 新建会话（标题由后端在首条消息后自动填充） */
  create: () =>
    request<ConversationDTO>('/conversation', {
      method: 'POST',
      data: {},
    }),

  /** 删除会话（软删除） */
  remove: (conversationId: number) =>
    request<null>(`/conversation/${conversationId}`, {
      method: 'DELETE',
    }),

  /** 历史消息（created_at 正序），当前只取最新一页 */
  listMessages: (conversationId: number) =>
    request<PageResult<MessageDTO>>(
      `/conversation/${conversationId}/messages`,
      {
        params: { page: 1, page_size: 50 },
      },
    ),
};
