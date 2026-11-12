import { RobotOutlined, UserOutlined } from '@ant-design/icons';
import {
  Bubble,
  Conversations,
  Prompts,
  Sender,
  Welcome,
} from '@ant-design/x';
import { XMarkdown } from '@ant-design/x-markdown';
import {
  useXChat,
  useXConversations,
} from '@ant-design/x-sdk';
import type { SSEOutput } from '@ant-design/x-sdk';
import { request } from '@umijs/max';
import { Button, Flex, message, Spin } from 'antd';
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { conversationApi } from '@/services/chat/conversationApi';
import {
  ChatRequestError,
  getChatProvider,
  removeChatProvider,
} from '@/services/chat/provider';
import type {
  ChatInput,
  ChatMessage,
  ConversationDTO,
  CurrentUser,
} from '@/services/chat/types';

/** 空态建议问题（统计年鉴主题） */
const PROMPT_ITEMS = [
  {
    key: '1',
    label: '2024 年我国国内生产总值是多少？',
  },
  {
    key: '2',
    label: '2024 年末全国人口有多少？',
  },
  {
    key: '3',
    label: '2024 年社会消费品零售总额增速如何？',
  },
];

const toConversationItem = (c: ConversationDTO) => ({
  key: String(c.id),
  label: c.title || '新对话',
});

const Chat: React.FC = () => {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [listLoading, setListLoading] = useState(true);

  const {
    conversations,
    activeConversationKey,
    setActiveConversationKey,
    addConversation,
    removeConversation,
    setConversations,
  } = useXConversations({
    defaultConversations: [],
    defaultActiveConversationKey: '',
  });

  const refreshConversations = useCallback(async () => {
    try {
      const page = await conversationApi.list();
      setConversations(page.items.map(toConversationItem));
    } catch {
      // 401 等错误已由全局拦截器处理
    }
  }, [setConversations]);

  // 每个会话一个独立 Provider 实例（use-x-chat 技能：多会话必须隔离状态）
  const provider = useMemo(
    () =>
      activeConversationKey
        ? getChatProvider(Number(activeConversationKey))
        : undefined,
    [activeConversationKey],
  );

  const {
    messages,
    onRequest,
    isRequesting,
    isDefaultMessagesRequesting,
    abort,
    queueRequest,
  } = useXChat<ChatMessage, ChatMessage, ChatInput, SSEOutput>({
    provider,
    conversationKey: activeConversationKey || undefined,
    requestPlaceholder: { role: 'assistant', content: '' },
    defaultMessages: async ({
      conversationKey,
    }: {
      conversationKey?: string;
    } = {}) => {
      if (!conversationKey) {
        return [];
      }
      try {
        const page = await conversationApi.listMessages(
          Number(conversationKey),
        );
        return page.items
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({
            message: {
              role: m.role as ChatMessage['role'],
              content: m.content,
            },
          }));
      } catch {
        return [];
      }
    },
    requestFallback: (_params, { error, messageInfo }) => {
      if (error.name === 'AbortError') {
        // 后端已落库部分回答，刷新后可见完整内容
        const partial = messageInfo?.message?.content?.trim();
        return {
          role: 'assistant',
          content: partial
            ? `${partial}\n\n> ⏹ 已停止生成`
            : '已停止生成',
        };
      }
      if (error instanceof ChatRequestError) {
        return { role: 'assistant', content: error.message };
      }
      return { role: 'assistant', content: '网络异常，请稍后重试' };
    },
  });

  // 挂载时加载用户与会话列表
  useEffect(() => {
    request('/auth/me')
      .then((data) => setUser(data))
      .catch(() => {
        // 401 已由全局 errorHandler 跳转登录页
      });
    conversationApi
      .list()
      .then((page) => {
        const items = page.items.map(toConversationItem);
        setConversations(items);
        if (items.length > 0) {
          setActiveConversationKey(items[0].key);
        }
      })
      .catch(() => {
        // 401 已由全局 errorHandler 处理
      })
      .finally(() => setListLoading(false));
    // 仅在挂载时执行
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 每轮问答结束后刷新列表（后端自动填充标题 / 更新排序）
  const prevIsRequesting = useRef(false);
  useEffect(() => {
    if (prevIsRequesting.current && !isRequesting) {
      refreshConversations();
    }
    prevIsRequesting.current = isRequesting;
  }, [isRequesting, refreshConversations]);

  const handleSubmit = useCallback(
    (content: string) => {
      const text = content.trim();
      if (!text) {
        return;
      }
      if (!activeConversationKey) {
        handleNewConversation(text);
        return;
      }
      onRequest({ content: text });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeConversationKey, onRequest],
  );

  const handleNewConversation = async (firstContent?: string) => {
    try {
      const conv = await conversationApi.create();
      addConversation(toConversationItem(conv));
      setActiveConversationKey(String(conv.id));
      if (firstContent) {
        // 等新会话的历史消息加载完成后自动发送
        queueRequest(String(conv.id), { content: firstContent });
      }
    } catch {
      // 错误已由全局拦截器提示
    }
  };

  const handleDeleteConversation = async (key: string) => {
    try {
      await conversationApi.remove(Number(key));
    } catch {
      return; // 错误已由全局拦截器提示
    }
    removeChatProvider(Number(key));
    removeConversation(key);
    if (activeConversationKey === key) {
      const next = conversations.find((c) => c.key !== key);
      // 没有剩余会话时清空当前会话，避免继续向已删除的会话发消息
      setActiveConversationKey(next?.key ?? '');
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    message.success('已退出登录');
    window.location.href = '/login';
  };

  const bubbleItems = messages.map(({ id, message: msg, status }) => ({
    key: id,
    role: msg.role,
    loading: status === 'loading',
    content:
      msg.role === 'assistant' && status !== 'loading' ? (
        <XMarkdown
          content={msg.content}
          streaming={{
            // 最后一块必须是 false，否则不完整片段不会被刷新为最终内容
            hasNextChunk: status === 'updating',
            tail: status === 'updating',
          }}
        />
      ) : (
        msg.content
      ),
  }));

  const showWelcome =
    !isDefaultMessagesRequesting && messages.length === 0;

  return (
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - 104px)',
        border: '1px solid #f0f0f0',
        borderRadius: 12,
        overflow: 'hidden',
        background: '#fff',
      }}
    >
      {/* 左侧：会话列表 + 用户区 */}
      <Flex
        vertical
        style={{ width: 260, borderRight: '1px solid #f0f0f0' }}
      >
        <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
          {listLoading ? (
            <Flex justify="center" style={{ paddingTop: 24 }}>
              <Spin />
            </Flex>
          ) : (
            <Conversations
              items={conversations}
              activeKey={activeConversationKey || undefined}
              onActiveChange={(key) => setActiveConversationKey(key)}
              creation={{
                onClick: () => handleNewConversation(),
              }}
              menu={(conversation) => ({
                items: [
                  { key: 'delete', label: '删除会话', danger: true },
                ],
                onClick: ({ key }) => {
                  if (key === 'delete') {
                    handleDeleteConversation(conversation.key);
                  }
                },
              })}
            />
          )}
        </div>
        <Flex
          justify="space-between"
          align="center"
          style={{
            padding: 12,
            borderTop: '1px solid #f0f0f0',
          }}
        >
          <span style={{ color: 'rgba(0,0,0,0.65)' }}>
            {user?.username ?? ''}
          </span>
          <Button size="small" danger onClick={logout}>
            退出登录
          </Button>
        </Flex>
      </Flex>

      {/* 右侧：消息流 + 输入框 */}
      <Flex vertical flex={1} style={{ minWidth: 0 }}>
        {isDefaultMessagesRequesting ? (
          <Flex
            flex={1}
            align="center"
            justify="center"
          >
            <Spin />
          </Flex>
        ) : (
          <>
            {showWelcome && (
              <Flex
                vertical
                align="center"
                style={{ paddingTop: 24, paddingBottom: 8 }}
              >
                <Welcome
                  icon={<RobotOutlined />}
                  title="你好，我是《中国统计年鉴 2025》智能助手"
                  description="我可以回答关于中国经济、人口、社会等统计数据的问题"
                  extra={
                    <Prompts
                      title="你可以这样问我"
                      items={PROMPT_ITEMS}
                      wrap
                      onItemClick={({ data }) =>
                        data.label && handleSubmit(String(data.label))
                      }
                    />
                  }
                />
              </Flex>
            )}
            <Bubble.List
              autoScroll
              style={{ flex: 1, minHeight: 0, padding: '0 16px' }}
              role={{
                user: {
                  placement: 'end',
                  variant: 'filled',
                  avatar: <UserOutlined />,
                },
                assistant: {
                  placement: 'start',
                  variant: 'outlined',
                  avatar: <RobotOutlined />,
                },
              }}
              items={bubbleItems}
            />
          </>
        )}
        <div style={{ padding: '0 16px 16px' }}>
          <Sender
            loading={isRequesting}
            onCancel={abort}
            onSubmit={handleSubmit}
            placeholder="请输入您的问题，Enter 发送，Shift+Enter 换行"
          />
        </div>
      </Flex>
    </div>
  );
};

export default Chat;
