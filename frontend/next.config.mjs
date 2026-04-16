/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode for better error detection
  reactStrictMode: true,

  // Optimize production builds
  swcMinify: true,

  // Disable TypeScript errors during build (we'll rely on pre-build checks)
  typescript: {
    ignoreBuildErrors: false,
  },

  // Disable ESLint during build
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Output standalone build for Docker
  output: 'standalone',

  // Image optimization
  images: {
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [],
  },

  // Enable compression
  compress: true,
};

export default nextConfig;
