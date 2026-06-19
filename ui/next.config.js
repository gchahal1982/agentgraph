/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: (process.env.AGENTGRAPH_SERVER ?? "http://localhost:8080") + "/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
