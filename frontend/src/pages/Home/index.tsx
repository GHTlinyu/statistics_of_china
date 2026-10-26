import { history, request } from '@umijs/max';
import { Button, Card, Descriptions, message, Space } from 'antd';
import React, { useEffect, useState } from 'react';

interface CurrentUser {
  user_id: number;
  username: string;
  role: string;
}

const Home: React.FC = () => {
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    request('/auth/me')
      .then((data) => setUser(data))
      .catch(() => {
        // 401 已由全局 errorHandler 跳转登录页
      });
  }, []);

  const logout = () => {
    localStorage.removeItem('token');
    message.success('已退出登录');
    history.push('/login');
  };

  return (
    <Card title="欢迎使用中国统计年鉴智能助手">
      {user ? (
        <Space direction="vertical">
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="用户 ID">{user.user_id}</Descriptions.Item>
            <Descriptions.Item label="用户名">{user.username}</Descriptions.Item>
            <Descriptions.Item label="角色">{user.role}</Descriptions.Item>
          </Descriptions>
          <Button danger onClick={logout}>
            退出登录
          </Button>
        </Space>
      ) : (
        <p>加载中...</p>
      )}
    </Card>
  );
};

export default Home;
