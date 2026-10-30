import { defineConfig } from '@umijs/max';

export default defineConfig({
  antd: {},
  request: {},
  // Umi 4 + 多异步 chunk 时避免 esbuild helper 冲突
  esbuildMinifyIIFE: true,
  layout: {
    title: '中国统计年鉴智能助手',
  },
  routes: [
    { path: '/', redirect: '/home' },
    {
      name: '首页',
      path: '/home',
      component: './Home',
    },
    {
      name: '登录',
      path: '/login',
      component: './Login',
      layout: false,
    },
  ],
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
      pathRewrite: { '^/api': '' },
    },
  },
  npmClient: 'pnpm',
});
