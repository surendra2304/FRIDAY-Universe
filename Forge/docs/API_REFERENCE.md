# Project FORGE — Consumer-Agnostic API Reference

Project FORGE is a standalone autonomous software engineering synthesis engine. It accepts high-level software goals from any programmatic caller or human operator, orchestrates multi-agent planning and synthesis fueled by AI-Universe, executes rigorous objective verification, and delivers production-ready deliverables.

---

## Authentication

All REST endpoints and WebSocket channels support API Key authentication:
- **Header:** `X-API-Key: <api_key>` or `Authorization: Bearer <api_key>`
- **Query Parameter (WebSockets):** `?api_key=<api_key>`

---

## REST Endpoints

### 1. Task Management (`/api/tasks`)

#### Submit Task
- **Endpoint:** `POST /api/tasks`
- **Description:** Submit a new high-level engineering goal for autonomous decomposition, synthesis, and verification.
- **Request Body:**
  ```json
  {
    "goal": "Build a responsive static personal portfolio website with dark mode",
    "requirements": ["Responsive layout", "Hero section", "Dark mode toggle"],
    "mode": "autonomous",
    "max_budget": 10.0,
    "webhook_url": "https://client.example.com/forge/webhook",
    "task_metadata": {
      "source": "my_orchestrator",
      "priority": "high",
      "deadline": "2026-08-28T00:00:00Z",
      "tags": ["frontend", "portfolio"]
    }
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "id": "task0127082026190000",
    "goal": "Build a responsive static personal portfolio website with dark mode",
    "requirements": ["Responsive layout", "Hero section", "Dark mode toggle"],
    "mode": "autonomous",
    "workspace_path": "workspaces/task0127082026190000",
    "max_budget": 10.0,
    "budget_consumed": 0.0,
    "state": "PENDING",
    "progress_percentage": 0,
    "metadata": {
      "priority": "high",
      "webhook_url": "https://client.example.com/forge/webhook"
    }
  }
  ```

#### List Tasks
- **Endpoint:** `GET /api/tasks`
- **Query Parameters:** `state`, `limit`, `since`, `include_archived`
- **Response (200 OK):**
  ```json
  [
    {
      "id": "task0127082026190000",
      "goal": "Build a responsive static personal portfolio website",
      "state": "COMPLETED",
      "progress_percentage": 100,
      "project_type": "website",
      "provenance_summary": "Generated via: AI-Universe (85.0%), Direct (15.0%)",
      "created_at": "2026-08-27T19:00:00Z"
    }
  ]
  ```

#### Get Task Status & Progress
- **Endpoint:** `GET /api/tasks/{task_id}`
- **Response (200 OK):**
  ```json
  {
    "id": "task0127082026190000",
    "state": "RUNNING",
    "progress_percentage": 65,
    "current_stage": "Implementation",
    "estimated_remaining_seconds": 12.5,
    "estimated_completion_at": "2026-08-27T19:05:12Z",
    "workspace_dirs": {
      "project": "workspaces/task0127082026190000/project",
      "artifacts": "artifacts/task0127082026190000"
    }
  }
  ```

#### Stream / Filter Logs
- **Endpoint:** `GET /api/tasks/{task_id}/logs`
- **Query Parameters:** `level` (DEBUG|INFO|WARNING|ERROR), `tail_lines`, `since`

#### Deep Workspace Inspection
- **Endpoint:** `GET /api/tasks/{task_id}/inspect`
- **Response (200 OK):**
  ```json
  {
    "task_id": "task0127082026190000",
    "files_created": [
      {"path": "index.html", "size_bytes": 2410, "line_count": 82, "provenance": "ai-universe"},
      {"path": "style.css", "size_bytes": 1820, "line_count": 64, "provenance": "ai-universe"}
    ],
    "verification_summary": {
      "passed": 4,
      "failed": 0,
      "checks": ["syntax", "security", "performance", "accessibility"]
    },
    "dependencies": ["pydantic", "fastapi"]
  }
  ```

#### Deliverable Artifacts
- **Endpoint:** `GET /api/tasks/{task_id}/artifacts` (Manifest) & `GET /api/tasks/{task_id}/artifacts/{filename}` (Raw Stream)

#### Cancel Task
- **Endpoint:** `POST /api/tasks/{task_id}/cancel`

#### Archive Task (Soft Delete)
- **Endpoint:** `DELETE /api/tasks/{task_id}`

---

## Optional Webhook Notifications

When a task is submitted with a `webhook_url`, FORGE dispatches lifecycle notifications using exponential backoff:

```json
{
  "event": "stage_completed",
  "timestamp": "2026-08-27T19:02:15Z",
  "task_id": "task0127082026190000",
  "data": {
    "stage": "Architecture",
    "progress": 35
  },
  "source": "forge"
}
```

Events emitted:
- `task_started`
- `stage_completed`
- `verification_result`
- `task_completed`
- `task_failed`

---

## WebSockets

### Task Stream
- **URL:** `ws://localhost:8000/ws/tasks/{task_id}`
- Streams real-time progress percentages, logs, and verification evidence for a single task.

### Global Broadcast Stream
- **URL:** `ws://localhost:8000/ws/tasks`
- Broadcasts lifecycle updates across all active tasks.

---

## Analytics Endpoints

- **`GET /api/analytics/summary`**: Aggregate metrics, duration averages, and success rates.
- **`GET /api/analytics/types`**: Category metrics (`website`, `cli`, `api`, `script`).
- **`GET /api/analytics/failures`**: Failure root-cause distribution.
