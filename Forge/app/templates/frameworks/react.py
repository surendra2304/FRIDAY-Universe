"""
React Component and Application Templates for Project FORGE.
Provides modern React 18+ component patterns with hooks, TypeScript interfaces, and React Testing Library tests.
"""

REACT_PACKAGE_JSON = """{
  "name": "{{app_name}}",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.395.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.6",
    "typescript": "^5.5.2",
    "vite": "^5.3.1"
  },
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest"
  }
}
"""

REACT_COMPONENT_TSX = """import React, { useState } from 'react';
import './{{component_name}}.css';

export interface {{component_name}}Props {
  title?: string;
  initialCount?: number;
  onAction?: (count: number) => void;
}

export const {{component_name}}: React.FC<{{component_name}}Props> = ({
  title = '{{component_name}} Widget',
  initialCount = 0,
  onAction,
}) => {
  const [count, setCount] = useState<number>(initialCount);

  const handleClick = () => {
    const next = count + 1;
    setCount(next);
    if (onAction) {
      onAction(next);
    }
  };

  return (
    <div className="{{component_name_lower}}-container" role="region" aria-label={title}>
      <h2 className="{{component_name_lower}}-title">{title}</h2>
      <p className="{{component_name_lower}}-display">Current Count: <strong>{count}</strong></p>
      <button
        type="button"
        className="{{component_name_lower}}-btn"
        onClick={handleClick}
        aria-label="Increment counter"
      >
        Increment
      </button>
    </div>
  );
};
"""

REACT_COMPONENT_CSS = """.{{component_name_lower}}-container {
  padding: 1.5rem;
  border-radius: 8px;
  background-color: #ffffff;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  font-family: system-ui, -apple-system, sans-serif;
  max-width: 400px;
}

.{{component_name_lower}}-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.75rem;
}

.{{component_name_lower}}-btn {
  background-color: #3b82f6;
  color: white;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.{{component_name_lower}}-btn:hover {
  background-color: #2563eb;
}

.{{component_name_lower}}-btn:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}
"""

REACT_COMPONENT_TEST_TSX = """import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { {{component_name}} } from './{{component_name}}';

describe('{{component_name}} Component', () => {
  test('renders with default title and count', () => {
    render(<{{component_name}} title="Test Widget" />);
    expect(screen.getByText('Test Widget')).toBeInTheDocument();
    expect(screen.getByText(/Current Count:/i)).toHaveTextContent('0');
  });

  test('increments counter on button click', () => {
    const handleAction = jest.fn();
    render(<{{component_name}} onAction={handleAction} />);
    const button = screen.getByRole('button', { name: /increment counter/i });
    fireEvent.click(button);
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(handleAction).toHaveBeenCalledWith(1);
  });
});
"""
