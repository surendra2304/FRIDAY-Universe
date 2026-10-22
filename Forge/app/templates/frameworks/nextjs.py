"""
Next.js Framework Templates for Project FORGE.
Provides starter code for Next.js App Router applications with API route handlers, layout, and Tailwind CSS configuration.
"""

NEXTJS_PACKAGE_JSON = """{
  "name": "{{app_name}}",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^14.2.4",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/node": "^20.14.9",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.5.2",
    "tailwindcss": "^3.4.4",
    "postcss": "^8.4.38",
    "autoprefixer": "^10.4.19"
  }
}
"""

NEXTJS_TSCONFIG_JSON = """{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""

NEXTJS_LAYOUT_TSX = """import React from 'react';
import './globals.css';

export const metadata = {
  title: '{{app_title}}',
  description: '{{description}}',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <header className="border-b bg-white p-4 shadow-sm">
          <div className="container mx-auto flex items-center justify-between">
            <h1 className="text-xl font-bold">{{app_title}}</h1>
          </div>
        </header>
        <main className="container mx-auto p-6">{children}</main>
      </body>
    </html>
  );
}
"""

NEXTJS_PAGE_TSX = """import React from 'react';

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
        {{app_title}}
      </h2>
      <p className="mt-4 text-lg text-gray-600">
        {{description}}
      </p>
      <div className="mt-8 flex gap-4">
        <button
          type="button"
          className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white shadow hover:bg-blue-700"
        >
          Get Started
        </button>
      </div>
    </div>
  );
}
"""

NEXTJS_API_ROUTE_TS = """import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    service: '{{app_name}} API',
  });
}
"""
