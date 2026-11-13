import { Conversations } from '@ant-design/x';
import { ConversationData } from '@ant-design/x-sdk';
import { Flex, Spin } from 'antd';

interface ConversationListProps {
  loading: boolean;
  conversations: ConversationData[];
  activeConversationKey: string | null;
  setActiveConversationKey: (key: string) => boolean;
  handleNewConversation: (firstContent?: string) => Promise<void>;
  handleDeleteConversation: (key: string) => Promise<void>;
}

const ConversationList = (props: ConversationListProps) => {
  const {
    loading,
    conversations,
    activeConversationKey,
    setActiveConversationKey,
    handleNewConversation,
    handleDeleteConversation,
  } = props;

  return (
    <Flex vertical style={{ width: 260, borderRight: '1px solid #f0f0f0' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
        {loading ? (
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
              items: [{ key: 'delete', label: '删除会话', danger: true }],
              onClick: ({ key }) => {
                if (key === 'delete') {
                  handleDeleteConversation(conversation.key);
                }
              },
            })}
          />
        )}
      </div>
    </Flex>
  );
};

export default ConversationList;
