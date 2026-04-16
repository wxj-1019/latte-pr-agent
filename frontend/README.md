# Latte PR Agent - Frontend

Enterprise AI Code Review System Frontend - A modern, responsive web interface for the Latte PR Agent.

## 🚀 Quick Start

### Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the application.

### Docker Development

```bash
# Build and run with Docker
docker-compose up web-dev

# Or use the deployment script
chmod +x deploy.sh
./deploy.sh --dev
```

## 📁 Project Structure

```
src/
├── app/                    # Next.js App Router
│   ├── api/               # API routes (mock endpoints)
│   ├── dashboard/         # Dashboard pages
│   └── page.tsx           # Landing page
├── components/            # React components
│   ├── dashboard/         # Dashboard components
│   ├── landing/           # Landing page components
│   ├── motion/            # Animation components
│   └── ui/                # Reusable UI components
├── hooks/                 # Custom React hooks
├── lib/                   # Utilities and API client
└── types/                 # TypeScript type definitions
```

## 🎨 Design System

The frontend uses a custom "Latte" design system:

- **Colors**: Warm espresso blacks, milk foam whites, and gold accents
- **Typography**: System fonts (SF Pro, Helvetica Neue, PingFang SC)
- **Components**: Glassmorphism cards, capsule buttons, status badges
- **Animations**: Framer Motion with Apple-style easing

## 🔧 Configuration

### Environment Variables

Create `.env.local` for development or `.env.production` for production:

```env
NEXT_PUBLIC_API_BASE=http://localhost:8000  # Backend API URL
NODE_ENV=production                         # Environment
```

### Backend Integration

The frontend expects the following backend endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/reviews` | GET | List reviews with filtering |
| `/api/reviews/:id` | GET | Review details |
| `/api/reviews/:id/findings` | GET | Review findings |
| `/api/metrics` | GET | Metrics data |
| `/api/config/:repoId` | GET/PUT | Project configuration |
| `/api/prompts/versions` | GET/POST | Prompt management |
| `/api/sse/reviews` | SSE | Real-time updates |

## 🐳 Docker Deployment

### Production

```bash
# Build and run production container
docker-compose up web -d

# Or use the deployment script
./deploy.sh --prod
```

### Development with Hot Reload

```bash
docker-compose up web-dev -d
```

### Docker Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild images
docker-compose build

# Check service status
docker-compose ps
```

## 🏗️ Build & Deployment

### Local Build

```bash
# Production build
npm run build

# Start production server
npm start
```

### Build Output

The build produces:
- Standalone output in `.next/standalone/`
- Static files in `.next/static/`
- Optimized images in multiple formats

### Health Check

The application includes a health check endpoint:
- `GET /api/health` - Returns service status

## 📊 Features

### Landing Page
- Responsive hero section with particle effects
- Interactive architecture visualization
- Feature showcase with bento grid layout
- Live dashboard preview

### Dashboard
- **Reviews**: Card-based list with real-time status updates
- **Review Details**: Three-panel layout (file tree, diff viewer, findings)
- **Metrics**: Charts and KPIs for review analytics
- **Configuration**: Visual editor for project settings
- **Prompts**: Version management for AI prompts

### Real-time Updates
- Server-Sent Events (SSE) for live status changes
- Automatic reconnection with exponential backoff
- Visual feedback for connection state

## 🛠️ Development

### Code Style

```bash
# Lint code
npm run lint

# Type checking
npx tsc --noEmit
```

### Component Guidelines

1. Use TypeScript for all components
2. Follow the Latte design system
3. Implement proper loading and error states
4. Support reduced motion preferences
5. Ensure keyboard navigation

### Testing

```bash
# Run build test
chmod +x build-test.sh
./build-test.sh
```

## 🔗 Integration with Backend

1. Update `NEXT_PUBLIC_API_BASE` to point to your backend
2. Ensure CORS is configured on the backend
3. Verify API endpoints match the expected format
4. Test SSE connectivity for real-time updates

## 📈 Performance

- Lighthouse performance target: ≥90
- First Contentful Paint: <2s
- Bundle size optimization with code splitting
- Image optimization with WebP/AVIF formats

## 🆘 Troubleshooting

### Build Issues
```bash
# Clean build artifacts
rm -rf .next node_modules

# Reinstall dependencies
npm ci

# Try alternative build method
./build-test.sh
```

### Docker Issues
```bash
# Reset Docker
docker-compose down -v
docker system prune -a

# Rebuild from scratch
docker-compose build --no-cache
```

### API Connection
- Verify backend is running
- Check CORS configuration
- Confirm endpoint URLs match
- Review browser console for errors

## 📄 License

MIT License - see the main project LICENSE file for details.

---

*Part of the Latte PR Agent - Enterprise AI Code Review System*
