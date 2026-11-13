import { defineConfig } from '@umijs/max';

export default defineConfig({
  antd: {},
  favicons: ['/favicon.png'],
  request: {},
  // Umi 4 + 多异步 chunk 时避免 esbuild helper 冲突
  esbuildMinifyIIFE: true,
  layout: {
    title: '中国统计年鉴智能助手',
  },
  routes: [
    { path: '/', redirect: '/home' },
    {
      name: '智能问答',
      path: '/home',
      component: './Chat',
      hideInMenu: true,
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
      target: 'https://creative-idea-generator.site',
      changeOrigin: true,
      pathRewrite: { '^/api': '/api' },
    },
  },
  npmClient: 'pnpm',
});
