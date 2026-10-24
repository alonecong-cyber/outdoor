/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // 同源代理后端 FastAPI，避免 CORS；后端默认 127.0.0.1:8000
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }];
  },
};

export default nextConfig;
