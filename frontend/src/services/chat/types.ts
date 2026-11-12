/**
 * 聊天相关类型：对齐后端 schema（backend/app/schema/chatDTO.py、conversationDTO.py）。
 */

/** 后端 SSE 事件（POST /conversation/{id}/chat 的 data 帧 JSON） */
export type ChatEvent =
  | { type: 'start'; data: { conversation_id: number } }
  | { type: 'token'; data: { content: string } }
  | { type: 'done'; data: { conversation_id: number; message_id: number | null } }
  | { type: 'error'; data: { code: string; message: string } };

/** 聊天消息（useXChat 的 ChatMessage 泛型） */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

/** useXChat 的输入参数 */
export interface ChatInput {
  content: string;
}

/** 后端 ConversationDTO */
export interface ConversationDTO {
  id: number;
  user_id: number;
  title: string | null;
  state: number;
  created_at: string;
  updated_at: string;
}

/** 后端 MessageDTO */
export interface MessageDTO {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  created_at: string;
}

/** 后端通用分页结构 */
export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** 当前登录用户（GET /auth/me） */
export interface CurrentUser {
  user_id: number;
  username: string;
  role: string;
}
