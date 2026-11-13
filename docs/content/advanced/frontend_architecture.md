Pagoda provides two distinct user interfaces: a modern React-based SPA (New UI) and a traditional Django template-based interface (Legacy UI). This document explains both interfaces, their features, and how to work with them.

## For Users

### Overview

#### New UI (React SPA)
- Modern, responsive single-page application
- Fast, client-side navigation
- Real-time updates and validations
- Consistent look and feel using Material-UI
- Internationalization support

#### Legacy UI (Django Templates)
- Traditional server-side rendered pages
- Direct database operations
- Stable and proven interface
- Simpler architecture for basic operations

### Key Features

#### Common Features
- Entity and attribute management
- User and group administration
- Access control management
- Advanced search capabilities
- History tracking
- Webhook management

#### New UI Specific Features
- Improved response times through API-based operations
- Modern form handling with real-time validation
- Enhanced user experience with instant feedback
- Consistent styling across all pages
- Mobile-friendly responsive design

#### Legacy UI Specific Features
- Direct database operations
- Server-side validation
- Traditional navigation pattern
- Simpler debugging process

### When to Use Which UI

#### Use New UI When
- Working with modern browsers
- Requiring real-time feedback
- Needing mobile-friendly interface
- Performing complex data operations
- Integrating with other modern web applications

#### Use Legacy UI When
- Requiring simpler, proven interface
- Working in environments with limited JavaScript support
- Needing direct database operations
- Performing basic CRUD operations

## For Developers

### Architecture Overview

#### New UI Architecture

##### Core Technologies
- React 18
- TypeScript
- Material-UI (MUI)
- react-router for routing
- react-hook-form for form management
- zod for schema validation
- i18next for internationalization

##### Directory Structure
```
frontend/src/
├── apiclient/      # API client wrapper
├── components/     # Reusable UI components
├── hooks/          # Custom React hooks
├── i18n/          # Internationalization
├── pages/         # Page components
├── repository/    # Data access layer
├── routes/        # Routing configuration
└── services/      # Business logic
```

##### Key Components
- API Client: Auto-generated from OpenAPI specs
- Form Management: react-hook-form with zod validation
- State Management: React hooks and context
- Routing: react-router with type-safe routes
- UI Components: Material-UI based components

#### Legacy UI Architecture

##### Core Technologies
- Django Templates
- jQuery (where needed)
- Bootstrap for styling

##### Template Structure
```
templates/
├── advanced_search/   # Search interface
├── edit_entry/       # Entry management
├── list_entry/       # Entry listing
├── registration/     # User registration
├── role/            # Role management
└── show_entry/      # Entry display
```

### Development Guidelines

#### Setting Up Development Environment

```bash
# Install dependencies
npm install

# Start development server
npm run watch

# Build for production
npm run build:production
```

#### Adding New Features

1. **New UI Development**
   - Follow React component patterns
   - Use TypeScript for type safety
   - Implement responsive design
   - Add appropriate test coverage
   - Update API client when needed

2. **Legacy UI Development**
   - Follow Django template patterns
   - Maintain backwards compatibility
   - Keep JavaScript usage minimal
   - Test across different browsers

#### Testing

1. **New UI Testing**
   - Unit tests with Jest
   - Component testing with React Testing Library
   - E2E testing when needed
   - i18n testing

2. **Legacy UI Testing**
   - Django template testing
   - Integration testing
   - Browser compatibility testing

### Performance Considerations

#### New UI
- Use React.memo for expensive components
- Implement proper code splitting
- Optimize bundle size
- Use appropriate caching strategies

##### Route bundle delivery

The application build keeps `ui.js` as its only initial script. React lazy
routes and their shared dependencies are loaded on demand as
`<id>.<contenthash>.ui.js`. Webpack resolves these files relative to the URL of
`ui.js`, so nested page URLs and a separate static asset host work without
additional template script tags. Do not enable initial vendor or runtime
chunks without updating both the application and login templates.

Keep imports on the dashboard's critical path pointed at the modules they
use. Importing through the broad component or library barrel can pull in
unrelated forms and date pickers, reducing the benefit of route splitting.

Deploy the complete application build output, including the hashed chunks,
before serving the corresponding `ui.js`. Django's `collectstatic` and the
default `CompressedManifestStaticFilesStorage` include these files. Retain
the original webpack filenames: the runtime references them directly, rather
than looking up Django's manifest. If static files use a CDN, publish all of
these files there as well. Invalidate the fixed-name `ui.js` when publishing
a new build.

Keep the previous release's hashed chunks available for already-open tabs
during rollout. If a chunk is no longer available, the existing error dialog
offers an explicit reload to fetch the current entry bundle; the application
does not automatically reload and discard in-progress input. Avoid cleaning
the entire `static/js` directory, which also contains legacy UI assets.

The library build is intentionally different: `webpack.library.config.js`
continues to inline lazy routes into the single `pagoda-core.js` UMD file.
Extension builders using that library retain their existing distribution
contract.

To verify production delivery locally:

```sh
npm run build:lib
npm run build:production
npm run test:e2e:install
npm run test:bundle-delivery
```

This gate checks the library's single-file output and uses Chromium with
mock APIs to verify deferred route downloads, client navigation, nested URL
and login entry points, a separate asset host, and recovery from a missing
chunk. It does not verify production CDN deployment or backend API behavior.

#### Legacy UI
- Minimize server-side processing
- Optimize template rendering
- Use appropriate caching
- Minimize database queries
