import {
  LockOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { history, request } from '@umijs/max';
import { Button, Card, Form, Input, message, Typography } from 'antd';
import React from 'react';

const { Title, Text } = Typography;

interface LoginForm {
  username: string;
  password: string;
  captcha_code: string;
}

interface CaptchaResponse {
  captcha_id: string;
  image: string;
  expires_in: number;
}

const Login: React.FC = () => {
  const [form] = Form.useForm<LoginForm>();
  const [loading, setLoading] = React.useState(false);
  const [captchaId, setCaptchaId] = React.useState('');
  const [captchaImage, setCaptchaImage] = React.useState('');
  const [captchaLoading, setCaptchaLoading] = React.useState(false);
  const captchaSeq = React.useRef(0);

  const refreshCaptcha = async () => {
    const seq = ++captchaSeq.current;
    setCaptchaLoading(true);
    try {
      const data: CaptchaResponse = await request('/auth/captcha');
      // 快速连点刷新时只采用最后一次响应，避免图片与 ID 错配
      if (seq !== captchaSeq.current) {
        return;
      }
      setCaptchaId(data.captcha_id);
      setCaptchaImage(data.image);
      form.setFieldValue('captcha_code', '');
    } catch {
      // 错误提示已由全局 errorHandler 统一处理
    } finally {
      if (seq === captchaSeq.current) {
        setCaptchaLoading(false);
      }
    }
  };

  React.useEffect(() => {
    refreshCaptcha();
  }, []);

  const onFinish = async (values: LoginForm) => {
    if (!captchaId) {
      message.error('验证码加载中，请稍后重试');
      return;
    }

    setLoading(true);
    try {
      const data = await request('/auth/login', {
        method: 'POST',
        data: {
          username: values.username,
          password: values.password,
          captcha_id: captchaId,
          captcha_code: values.captcha_code,
        },
      });
      localStorage.setItem('token', data.access_token);
      message.success('登录成功');
      history.push('/home');
    } catch {
      // 验证码一次性使用，失败后立即刷新，避免用旧验证码再次提交
      setCaptchaId('');
      form.setFieldValue('captcha_code', '');
      refreshCaptcha();
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
        <Form<LoginForm> form={form} onFinish={onFinish}>
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
          <Form.Item
            name="captcha_code"
            rules={[{ required: true, message: '请输入验证码' }]}
          >
            <Input
              prefix={<SafetyCertificateOutlined />}
              placeholder="验证码"
              maxLength={8}
              suffix={
                captchaImage ? (
                  <img
                    src={captchaImage}
                    alt="验证码"
                    title="点击刷新验证码"
                    onClick={refreshCaptcha}
                    style={{
                      height: 28,
                      display: 'block',
                      cursor: 'pointer',
                    }}
                  />
                ) : (
                  <Button
                    type="link"
                    size="small"
                    loading={captchaLoading}
                    onClick={refreshCaptcha}
                    style={{ padding: 0 }}
                  >
                    获取验证码
                  </Button>
                )
              }
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              block
              loading={loading || captchaLoading}
            >
              登录
            </Button>
          </Form.Item>
        </Form>
        <Text type="secondary" style={{ fontSize: 12 }}>
          还没有账号？请调用 POST /auth/register 注册（需同时提交验证码）
        </Text>
      </Card>
    </div>
  );
};

export default Login;
