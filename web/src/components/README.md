# Component Organization Guide

## Overview

Ampy3 uses a component-based architecture with React. This guide clarifies the component structure and how to organize new components.

## Directory Structure

```
src/components/
├── Layout/                  # Page layout wrappers
│   └── [Add here as needed]
└── README.md               # This file
```

## Component Types

### Page Components
- Located in `src/pages/`
- Represent top-level routes in the application
- Example: `Settings.tsx` for the `/settings` route
- Can contain sub-components and manage page-level state

### Feature Components
- Located in feature folders like `src/components/Settings/`
- Implement specific features or domain logic
- Reusable within the feature context
- Example: `SettingsLayout.tsx`

### Common/Shared Components
- Located in `src/components/Common/`
- Used across multiple features
- Should be stateless or have minimal state
- Examples: Buttons, modals, form inputs, cards
- Currently WIP - add as needed

### Layout Components
- Located in `src/components/Layout/`
- Provide consistent structure and styling across pages
- Examples: Header, footer, sidebar, navigation
- Currently WIP - add as needed

## Naming Conventions

- **Files**: PascalCase (e.g., `SettingsLayout.tsx`)
- **Components**: PascalCase export (e.g., `export function SettingsLayout()`)
- **CSS Modules**: `.module.css` for component-scoped styles (e.g., `SettingsLayout.module.css`)
- **Global styles**: `globals.css` in `src/`

## Styling

- Primary: Tailwind CSS utility classes
- Secondary: CSS Modules for component-specific styles
- Avoid inline styles except for dynamic values

## State Management

- React hooks for local component state (`useState`, `useContext`)
- Custom hooks for shared logic (example: `useScheduledSyncs`)
- Context API for app-level state (authentication, theme, etc.)
- Consider Redux or Zustand if state complexity increases

## Imports

Import order in React components:

1. React and library imports
2. Type/interface imports
3. Internal component imports
4. Hook imports
5. Style imports

Example:
```typescript
import React, { useState, useCallback } from "react";
import { useRouter } from "next/router";

import type { TrackTarget } from "../api/syncs";
import { SyncItem } from "./SyncItem";
import { useScheduledSyncs } from "../hooks/useScheduledSyncs";
import "./MyComponent.css";
```

## Best Practices

1. **Colocate related code**: Keep components with their styles and tests
2. **Extract logic to hooks**: Use custom hooks for complex state/side-effects
3. **Keep components focused**: Each component should have a single responsibility
4. **Document props**: Use JSDoc or TypeScript interfaces for clarity
5. **Lazy load if needed**: Use `React.lazy()` for code splitting on heavy components
6. **Test components**: Add `.test.tsx` files alongside components
7. **Avoid prop drilling**: Use Context API or custom hooks for deeply nested data

## Adding New Components

1. Create a folder in the appropriate directory
2. Add the component file (e.g., `MyComponent.tsx`)
3. Add styles if needed (e.g., `MyComponent.css`)
4. Export from an `index.ts` if using a folder structure
5. Update this README if creating a new feature area

## Examples

### Simple Component
```typescript
import React from "react";

interface MyComponentProps {
  title: string;
  onAction?: () => void;
}

export function MyComponent({ title, onAction }: MyComponentProps) {
  return (
    <div className="p-4 border rounded">
      <h2 className="font-bold">{title}</h2>
      {onAction && (
        <button onClick={onAction} className="mt-2 px-4 py-2 bg-blue-600 text-white rounded">
          Action
        </button>
      )}
    </div>
  );
}
```

### Component with Custom Hook
```typescript
import React from "react";
import { useScheduledSyncs } from "../hooks/useScheduledSyncs";

export function SyncList() {
  const { syncs, loading } = useScheduledSyncs();

  return (
    <div>
      {/* Render syncs */}
    </div>
  );
}
```

## Migration Notes

- API clients live in `src/api/<feature>/` and are imported directly by pages and hooks.
