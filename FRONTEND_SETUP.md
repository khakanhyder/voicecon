# Frontend Setup Guide

Complete guide to set up and run the Voicecon frontend application.

## Quick Start

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000` to see the application.

## Step-by-Step Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

This will install all required packages including:
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Shadcn/ui components
- React Query
- Axios
- Zustand

### 2. Configure Environment

```bash
cp .env.local.example .env.local
```

Edit `.env.local` and set:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_APP_NAME=Voicecon
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 3. Start Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

## Features Overview

### 🔐 Authentication
- **Login**: `/login` - Email/password authentication
- **Register**: `/register` - New user registration
- **Token Management**: Automatic token refresh
- **Protected Routes**: Dashboard requires authentication

### 📊 Dashboard
- **Overview**: Statistics and quick actions
- **Sidebar Navigation**: Easy access to all features
- **Responsive Layout**: Works on desktop and mobile

### 🎨 UI Components
- **Shadcn/ui**: Beautiful, accessible components
- **Tailwind CSS**: Utility-first styling
- **Dark Mode Ready**: Theme system configured
- **Icons**: Lucide React icons

## File Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── (auth)/              # Auth pages
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/         # Protected pages
│   │   │   ├── agents/
│   │   │   ├── calls/
│   │   │   ├── integrations/
│   │   │   ├── workflows/
│   │   │   ├── analytics/
│   │   │   ├── marketplace/
│   │   │   └── settings/
│   │   ├── layout.tsx           # Root layout
│   │   ├── page.tsx             # Landing page
│   │   ├── providers.tsx        # React Query provider
│   │   └── globals.css          # Global styles
│   │
│   ├── components/
│   │   ├── ui/                  # Shadcn components
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── card.tsx
│   │   │   └── label.tsx
│   │   └── layout/              # Layout components
│   │       ├── Header.tsx
│   │       └── Sidebar.tsx
│   │
│   ├── hooks/
│   │   └── useAuth.ts           # Auth hook
│   │
│   ├── lib/
│   │   ├── api.ts               # API client
│   │   ├── auth.ts              # Auth utilities
│   │   ├── constants.ts         # Constants
│   │   └── utils.ts             # Utils
│   │
│   ├── store/
│   │   └── authStore.ts         # Zustand store
│   │
│   └── types/
│       └── index.ts             # TypeScript types
│
├── public/                      # Static files
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
└── .env.local.example
```

## Development Workflow

### 1. Running the App

```bash
# Development mode (hot reload)
npm run dev

# Production build
npm run build
npm run start
```

### 2. Code Quality

```bash
# Lint code
npm run lint

# Format code
npm run format

# Type check
npm run type-check
```

### 3. Testing Authentication

1. Start the backend server (port 8000)
2. Start the frontend (port 3000)
3. Go to `http://localhost:3000`
4. Click "Get Started" or "Login"
5. Register a new account
6. Login with your credentials
7. Access the dashboard

## Key Features Implemented

### ✅ Authentication Flow
- JWT token storage in localStorage
- Automatic token refresh on 401 errors
- Protected route middleware
- Login/Logout functionality

### ✅ API Integration
- Axios client with interceptors
- Token management
- Error handling
- Request/Response types

### ✅ State Management
- Zustand for auth state
- React Query for server state
- Persistent auth across page reloads

### ✅ UI Components
- Responsive sidebar navigation
- Header with user info
- Beautiful form components
- Card-based layouts

### ✅ Pages Created
- Landing page
- Login page
- Register page
- Dashboard overview
- Dashboard layout (ready for sub-pages)

## Next Steps

### Immediate (Days 1-2)
1. **Agent Management Pages**
   - Agent list page
   - Agent create/edit form
   - Agent details view

2. **Integration Pages**
   - Available integrations list
   - Integration setup flow
   - Connected integrations view

### Week 2
3. **Workflow Builder**
   - Visual flow builder with React Flow
   - Trigger/action configuration
   - Workflow execution history

4. **Call Management**
   - Call logs list
   - Call details with transcript
   - Audio playback

### Week 3
5. **Analytics Dashboard**
   - Charts with Recharts
   - Real-time metrics
   - Export functionality

6. **Settings Pages**
   - Profile management
   - API keys
   - Billing
   - Team management

## Troubleshooting

### Port Already in Use
```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Or use a different port
PORT=3001 npm run dev
```

### Module Not Found
```bash
# Clear cache and reinstall
rm -rf node_modules .next
npm install
```

### API Connection Issues
- Ensure backend is running on port 8000
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Verify CORS settings in backend

### TypeScript Errors
```bash
# Clear Next.js cache
rm -rf .next

# Rebuild
npm run build
```

## Performance Tips

1. **Image Optimization**: Use Next.js `Image` component
2. **Code Splitting**: Use dynamic imports for large components
3. **Lazy Loading**: Load components when needed
4. **Caching**: React Query handles caching automatically

## Security Best Practices

1. **Never commit `.env.local`** to git
2. **Don't store sensitive data** in localStorage
3. **Always validate user input** on both client and server
4. **Use HTTPS** in production
5. **Keep dependencies updated** regularly

## Deployment

### Vercel (Recommended)
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

### Docker
```bash
# Build image
docker build -t voicecon-frontend .

# Run container
docker run -p 3000:3000 voicecon-frontend
```

### Manual Build
```bash
# Build
npm run build

# Start
npm run start
```

## Support

For issues or questions:
- Check [main README](/README.md)
- Review [Getting Started guide](/GETTING_STARTED.md)
- Open an issue on GitHub

---

Happy coding! 🚀
