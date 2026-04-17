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

  // Security headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
          },
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
