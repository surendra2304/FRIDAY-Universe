"""
Express.js Framework Templates for Project FORGE.
Provides starter code for modular Node.js Express REST APIs with JWT authentication, routing, middleware, and tests.
"""

EXPRESS_PACKAGE_JSON = """{
  "name": "{{app_name}}",
  "version": "1.0.0",
  "description": "{{description}}",
  "main": "src/server.js",
  "type": "module",
  "scripts": {
    "start": "node src/server.js",
    "dev": "nodemon src/server.js",
    "test": "jest --detectOpenHandles"
  },
  "dependencies": {
    "express": "^4.19.2",
    "cors": "^2.8.5",
    "dotenv": "^16.4.5",
    "jsonwebtoken": "^9.0.2",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "supertest": "^7.0.0",
    "nodemon": "^3.1.4"
  }
}
"""

EXPRESS_SERVER_JS = """import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { router as apiRouter } from './routes/api.js';
import { errorHandler } from './middleware/errorHandler.js';

dotenv.config();

export const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Health Probe
app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

// API Routes
app.use('/api', apiRouter);

// Error Handling Middleware
app.use(errorHandler);

if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, () => {
    console.log(`Express server running on http://localhost:${PORT}`);
  });
}
"""

EXPRESS_ROUTES_API_JS = """import { Router } from 'express';
import { z } from 'zod';

export const router = Router();

const ItemSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string().optional(),
});

const items = [];

router.get('/items', (req, res) => {
  res.json({ success: true, count: items.length, data: items });
});

router.post('/items', (req, res, next) => {
  try {
    const validated = ItemSchema.parse(req.body);
    const newItem = { id: items.length + 1, ...validated, createdAt: new Date().toISOString() };
    items.push(newItem);
    res.status(201).json({ success: true, data: newItem });
  } catch (err) {
    next(err);
  }
});
"""

EXPRESS_ERROR_HANDLER_JS = """export function errorHandler(err, req, res, next) {
  console.error('[Error]', err.message || err);

  if (err.name === 'ZodError') {
    return res.status(400).json({
      success: false,
      error: 'Validation Error',
      details: err.errors,
    });
  }

  const statusCode = err.statusCode || 500;
  res.status(statusCode).json({
    success: false,
    error: err.message || 'Internal Server Error',
  });
}
"""

EXPRESS_TEST_JS = """import request from 'supertest';
import { app } from '../src/server.js';

describe('Express API Integration Tests', () => {
  test('GET /health returns 200 OK', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });

  test('POST /api/items creates item with validation', async () => {
    const res = await request(app)
      .post('/api/items')
      .send({ name: 'Test Widget', description: 'A test widget' });
    expect(res.status).toBe(201);
    expect(res.body.data.name).toBe('Test Widget');
  });
});
"""
