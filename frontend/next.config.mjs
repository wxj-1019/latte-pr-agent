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

  // Enable ESLint during build (default)
  eslint: {
    ignoreDuringBuilds: false,
  },

  // Output standalone build for Docker (production only)
  output: process.env.NODE_ENV === 'production' ? 'standalone' : undefined,

  // Ensure clean builds and consistent output directory
  distDir: '.next',
  cleanDistDir: true,

  // Image optimization
  images: {
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [],
  },

  // Enable compression
  compress: true,

  // Explicitly disable source maps in production to avoid 404s for missing .map files
  productionBrowserSourceMaps: false,

  experimental: {
    missingSuspenseWithCSRBailout: false,
  },

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
          {
            key: 'Content-Security-Policy',
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; img-src 'self' data:; font-src 'self';",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
