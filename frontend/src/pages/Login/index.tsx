import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { history, request } from '@umijs/max';
import { Button, Card, Form, Input, message, Typography } from 'antd';
import React from 'react';

const { Title, Text } = Typography;

interface LoginForm {
  username: string;
  password: string;
}

const Login: React.FC = () => {
  const [loading, setLoading] = React.useState(false);

  const onFinish = async (values: LoginForm) => {
    setLoading(true);
    try {
      const data = await request('/auth/login', {
        method: 'POST',
        data: values,
      });
      localStorage.setItem('token', data.access_token);
      message.success('登录成功');
      history.push('/home');
    } catch {
      // 错误提示已由全局 errorHandler 统一处理
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f0f2f5',
      }}
    >
      <Card style={{ width: 360 }}>
        <Title level={3} style={{ textAlign: 'center' }}>
          中国统计年鉴智能助手
        </Title>
        <Form<LoginForm> onFinish={onFinish}>
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>
        <Text type="secondary" style={{ fontSize: 12 }}>
          还没有账号？可通过接口 POST /auth/register 注册
        </Text>
      </Card>
    </div>
  );
};

export default Login;
