# OmniRetail AI - Task Breakdown

## Phase 1: Foundation & Data Pipeline

### Task 1.1: Database Schema and Docker Setup
**Description:** Create PostgreSQL schema, Docker Compose, and environment configuration.
**Acceptance criteria:**
- PostgreSQL starts in Docker Compose.
- Schema tables are created successfully.
- Environment variables are configured securely.

### Task 1.2: CSV Cleaning and ETL
**Description:** Build a Python ETL pipeline that cleans CSVs, normalizes dates, and loads data into PostgreSQL.
**Acceptance criteria:**
- All CSVs are parsed and normalized.
- Date formats are standardized to `YYYY-MM-DD`.
- Data inserts into normalized schema without errors.

### Task 1.3: Base FastAPI App and Health Check
**Description:** Create an initial FastAPI application with a health endpoint and simple query endpoint.
**Acceptance criteria:**
- `/health` returns `200 OK`.
- `/products` returns sample product records.

---

## Phase 2: Core Agent Development

### Task 2.1: SQL Agent Implementation
**Description:** Build a LangChain SQL Agent that translates natural language into SQL and executes queries.
**Acceptance criteria:**
- Agent generates SQL for intent-based queries.
- Queries execute safely against PostgreSQL.
- Results are returned as JSON.

### Task 2.2: Python Analytics Agent
**Description:** Build a Python Agent that receives SQL results and performs additional analytics and chart generation.
**Acceptance criteria:**
- Agent can compute KPIs and trends.
- Generates charts as PNG/Plotly JSON.
- Returns text + chart references.

### Task 2.3: LangGraph Router and Workflow
**Description:** Create LangGraph workflow with Router, SQL Agent, Python Agent, and Output Formatter.
**Acceptance criteria:**
- Queries are routed to the correct agent(s).
- Cross-node state persists across workflow.
- Output formatting node composes final answer.

---

## Phase 3: LLMOps & UI

### Task 3.1: LangSmith Integration
**Description:** Add LangSmith tracing for all LLM calls and metadata.
**Acceptance criteria:**
- Every prompt/call is logged.
- Token usage and latency are visible.
- Cost analytics can be queried.

### Task 3.2: Streamlit Chat UI
**Description:** Build a Streamlit interface for natural language questions, context display, and chart rendering.
**Acceptance criteria:**
- User enters query and receives response.
- Charts display inline.
- Conversational history persists.

### Task 3.3: Conversation Memory and Context
**Description:** Implement memory for user session context to handle follow-up queries.
**Acceptance criteria:**
- System responds correctly to follow-up questions.
- Memory is scoped per session.

---

## Phase 4: Deployment & Hardening

### Task 4.1: Production Docker Build
**Description:** Harden Docker configuration, multi-stage build, and environment security.
**Acceptance criteria:**
- `docker-compose up --build` succeeds.
- App uses production settings.

### Task 4.2: Homelab Deployment
**Description:** Deploy app to Ubuntu VM on Proxmox, configure reverse proxy and SSL.
**Acceptance criteria:**
- App accessible via homelab hostname.
- SSL enabled.

### Task 4.3: Monitoring and Backup
**Description:** Add logging, monitoring, and backup/restore procedures.
**Acceptance criteria:**
- Logs are persisted.
- Metrics available.
- Database backups can be restored.
