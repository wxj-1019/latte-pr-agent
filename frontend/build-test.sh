#!/bin/bash

# Build test script that works around permission issues
set -e

echo "🔧 Testing build process..."

# Clean up any existing build artifacts
echo "🧹 Cleaning up..."
rm -rf .next 2>/dev/null || true
rm -rf out 2>/dev/null || true

# Create a temporary directory for build
TEMP_DIR=$(mktemp -d)
echo "📁 Using temporary directory: $TEMP_DIR"

# Copy source files
echo "📋 Copying source files..."
cp -r src package.json package-lock.json next.config.mjs tailwind.config.ts tsconfig.json postcss.config.mjs public "$TEMP_DIR/"

# Navigate to temp directory
cd "$TEMP_DIR"

# Install dependencies
echo "📦 Installing dependencies..."
npm ci --only=production

# Try to build
echo "🏗️  Attempting build..."
if npm run build 2>&1 | tee build.log; then
    echo "✅ Build successful!"

    # Check build output
    if [ -d ".next" ]; then
        echo "📊 Build statistics:"
        du -sh .next || true
        echo "🎉 Build test passed!"
    else
        echo "❌ Build directory not created"
        exit 1
    fi
else
    echo "❌ Build failed"
    echo "📄 Last 50 lines of build log:"
    tail -50 build.log
    exit 1
fi

# Clean up
cd -
rm -rf "$TEMP_DIR"
echo "🧹 Cleanup complete"