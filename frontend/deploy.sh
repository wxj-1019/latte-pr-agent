#!/bin/bash

# Latte PR Agent Frontend Deployment Script
set -e

echo "🚀 Starting Latte PR Agent Frontend Deployment"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# Parse command line arguments
MODE="production"
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            MODE="development"
            shift
            ;;
        --prod)
            MODE="production"
            shift
            ;;
        --help)
            echo "Usage: ./deploy.sh [--dev|--prod]"
            echo "  --dev    Deploy development version with hot reload"
            echo "  --prod   Deploy production version (default)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "📦 Deployment mode: $MODE"

# Set environment variables
if [ ! -f .env.production ]; then
    echo "⚠️  Warning: .env.production not found, creating from template..."
    cp .env.example .env.production 2>/dev/null || echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.production
fi

if [ "$MODE" = "development" ]; then
    echo "🔧 Starting development deployment..."
    docker-compose -f docker-compose.yml up web-dev -d
else
    echo "🏗️  Building production image..."
    docker-compose -f docker-compose.yml build web

    echo "🚀 Starting production deployment..."
    docker-compose -f docker-compose.yml up web -d
fi

echo "✅ Deployment completed!"
echo ""
echo "📊 Service Information:"
echo "   - Frontend URL: http://localhost:3000"
echo "   - Dashboard: http://localhost:3000/dashboard"
echo "   - Health check: http://localhost:3000/health"
echo ""
echo "🔍 Check logs: docker-compose logs -f"
echo "🛑 Stop services: docker-compose down"