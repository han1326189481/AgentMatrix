/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // 静态导出模式（Tauri / EXE 打包需要）
  output: 'export',
  // 静态导出时禁用 next/image 优化（需使用 <img>）
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
    // 若未来需要动态端口，可使用 Tauri withGlobalTauri 注入
    // 参考: https://v2.tauri.app/reference/javascript/api/namespacecore/
  },
  // 静态导出不支持 headers() 配置，CORS 由后端 FastAPI 处理
  // ESLint 配置在父目录，构建时跳过（ESLint 在 CI 中单独运行）
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;