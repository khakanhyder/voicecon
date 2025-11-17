# Voicecon Frontend

Modern Next.js 14 frontend application for Voicecon voice AI platform.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: Shadcn/ui
- **State Management**: Zustand
- **Data Fetching**: React Query (TanStack Query)
- **Forms**: React Hook Form + Zod
- **HTTP Client**: Axios
- **Icons**: Lucide React

## Getting Started

### Prerequisites

- Node.js 20+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.local.example .env.local

# Start development server
npm run dev
```

The application will be available at `http://localhost:3000`

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── (auth)/            # Authentication pages (login, register)
│   ├── (dashboard)/       # Protected dashboard pages
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Landing page
│   └── providers.tsx      # React Query provider
│
├── components/
│   ├── ui/                # Shadcn/ui components
│   └── layout/            # Layout components (Header, Sidebar)
│
├── hooks/                 # Custom React hooks
│   └── useAuth.ts         # Authentication hook
│
├── lib/                   # Utilities and configurations
│   ├── api.ts             # Axios API client
│   ├── auth.ts            # Auth utilities
│   ├── constants.ts       # App constants
│   └── utils.ts           # Helper functions
│
├── store/                 # Zustand stores
│   └── authStore.ts       # Authentication state
│
└── types/                 # TypeScript type definitions
    └── index.ts
```

## Available Scripts

```bash
# Development
npm run dev              # Start development server
npm run build            # Build for production
npm run start            # Start production server

# Code Quality
npm run lint             # Run ESLint
npm run format           # Format code with Prettier
npm run type-check       # Run TypeScript type checking
```

## Environment Variables

See `.env.local.example` for required environment variables:

- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)
- `NEXT_PUBLIC_WS_URL` - WebSocket URL (default: ws://localhost:8000)
- `NEXT_PUBLIC_APP_NAME` - Application name
- `NEXT_PUBLIC_APP_URL` - Frontend URL

## Features

### Authentication
- JWT-based authentication
- Login and registration pages
- Token refresh mechanism
- Protected routes

### Dashboard
- Overview with statistics
- Quick actions
- Recent activity feed

### Layout
- Responsive sidebar navigation
- Header with user menu
- Dark mode support (coming soon)

## Development Guidelines

### Adding New Pages

1. Create page in `src/app/(dashboard)/`
2. Add route to sidebar navigation in `components/layout/Sidebar.tsx`
3. Implement page component with proper error handling

### Adding API Endpoints

1. Define endpoint in `lib/constants.ts`
2. Create service function in appropriate file
3. Use React Query hook for data fetching
4. Handle loading and error states

### State Management

- Use Zustand for global state (auth, theme)
- Use React Query for server state
- Use React hooks for component state

## Contributing

See main project README for contribution guidelines.

## License

See main project LICENSE file.
