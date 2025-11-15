# Neurosurgical DCS - Frontend

Medical-grade frontend application for discharge summary generation.

## Technology Stack

- **Framework**: Vue 3 (Composition API + TypeScript)
- **Build Tool**: Vite
- **State Management**: Pinia
- **Routing**: Vue Router
- **HTTP Client**: Axios + Vue Query
- **Styling**: Tailwind CSS
- **UI Components**: Headless UI + Custom
- **Testing**: Vitest (unit) + Playwright (E2E)

## Architecture

### Two-Workflow Design

1. **Clinical Workflow** (`/`) - Write permission
   - Single-page, progressive disclosure (Steps 1 → 2 → 3)
   - Step 1: Document Input (Bulk or Individual)
   - Step 2: Review & Verify (Human Gate - MANDATORY)
   - Step 3: Summary Generation & Review

2. **Admin Dashboard** (`/admin`) - Approve permission
   - Learning pattern approval
   - System monitoring
   - Audit logs

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on http://localhost:8000

### Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env.development
```

### Development

```bash
# Run development server
npm run dev

# Visit http://localhost:3000
```

### Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

### Testing

```bash
# Run unit tests
npm run test:unit

# Run unit tests with coverage
npm run test:coverage

# Run E2E tests
npm run test:e2e
```

## Project Structure

```
src/
├── views/           # Main application views
├── components/      # Vue components
├── composables/     # Business logic hooks
├── services/        # API services
├── stores/          # Pinia stores
├── types/           # TypeScript types
├── utils/           # Utility functions
├── router.ts        # Vue Router configuration
└── main.ts          # Application entry point
```

## Safety Architecture

### Multi-Note Processor

The bulk import feature enforces a **mandatory human verification step**:

```
Bulk Text → Parse (Suggestions) → Human Review → Process
            ↓                      ↓
         Parse-only            Verified types
         endpoint              & dates only
```

**Safety Guarantees**:
- ✅ Parse endpoint (`/api/bulk-import/parse`) only suggests, never processes
- ✅ Human must confirm/correct all document types
- ✅ All processing goes through existing `/api/process` endpoint
- ✅ No bypass paths exist

## Development Guidelines

### Type Safety

- All components use TypeScript
- Strict mode enabled
- Types match backend API contracts

### Testing

- **Target**: >90% unit test coverage
- **E2E**: Critical workflows (login, bulk import, summary generation)
- **Safety tests**: Verify human gate enforcement

### Code Quality

```bash
# Lint
npm run lint

# Format
npm run format
```

## Deployment

See `DEPLOYMENT_GUIDE.md` in the root directory.

## License

Proprietary - Internal use only
