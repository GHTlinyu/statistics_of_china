import { message } from 'antd';
import type { RequestConfig } from '@umijs/max';

/**
 * 全局请求配置：
 * - 自动携带 Bearer token
 * - 剥离后端统一响应结构 {code, message, data}，业务代码直接拿 data
 * - 统一错误提示；401 清除 token 并跳转登录页
 */
export const request: RequestConfig = {
  baseURL: '/api',
  timeout: 10000,
  requestInterceptors: [
    (config: any) => {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers = {
          ...config.headers,
          Authorization: `Bearer ${token}`,
        };
      }
      return config;
    },
  ],
  responseInterceptors: [
    (response: any) => {
      const body = response.data;
      if (body && typeof body === 'object' && 'code' in body) {
        if (body.code === 200) {
          response.data = body.data;
        }
      }
      return response;
    },
  ],
  errorConfig: {
    errorHandler: (error: any) => {
      const res = error?.response;
      const apiMessage = res?.data?.message;
      if (res?.status === 401) {
        localStorage.removeItem('token');
        message.error(apiMessage || '登录已过期，请重新登录');
        window.location.href = '/login';
        return;
      }
      message.error(apiMessage || error?.message || '网络错误');
    },
  },
};
