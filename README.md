# AgentMatrix

**A Multi-Agent Collaboration Platform with Hybrid Local-Cloud Inference and Self-Learning Capabilities**

AgentMatrix is a desktop AI assistant built around a 5-Agent responsibility chain workflow. It is designed to minimize cloud LLM dependency through intelligent routing, while continuously improving via a closed-loop self-learning system. The platform runs entirely on consumer-grade hardware (8GB VRAM) and ships as a Tauri desktop application.

> This project serves as a graduation thesis research subject and graduate school interview defense project, focused on cognitive architecture design, local-cloud hybrid inference, and self-evolving AI systems.

---

## Table of Contents

- [Highlights](#highlights)
- [Architecture Overview](#architecture-overview)
- [Core Features](#core-features)
  - [1. 5-Agent Responsibility Chain Workflow](#1-5-agent-responsibility-chain-workflow)
  - [2. Self-Learning Skill Engine](#2-self-learning-skill-engine)
  - [3. User Profiling & Long-Term Memory](#3-user-profiling--long-term-memory)
  - [4. Hybrid Local-Cloud Inference](#4-hybrid-local-cloud-inference)
  - [5. Vision Model Integration](#5-vision-model-integration)
  - [6. Web Search Plugin with Self-Learning Knowledge Base](#6-web-search-plugin-with-self-learning-knowledge-base)
  - [7. Complaint Detection & Clarification Mechanism](#7-complaint-detection--clarification-mechanism)
  - [8. Multi-Sandbox Isolation](#8-multi-sandbox-isolation)
  - [9. Multi-Format Export](#9-multi-format-export)
  - [10. Graph-Based Cognitive Architecture](#10-graph-based-cognitive-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [License](#license)

---

## Highlights

- **Self-Learning System**: A closed loop where Review Agent feedback is automatically collected, filtered by confidence, and used to generate skill patches that improve the system over time — no manual retraining required.
- **User Profiling**: A 7-dimensional cognitive profile (identity, goals, preferences, abilities, projects, memory, context) that auto-evolves based on conversation history, combined with a long-term memory store that scores and prunes memories by importance, recency, and access frequency.
- **Hybrid Local-Cloud Inference**: A dual-threshold routing mechanism (difficulty + review score) dynamically decides whether a task is handled locally or enhanced by the cloud, with a strong-signal-word correction to counter LLM underestimation of task difficulty.
- **Vision Model**: MiniCPM-V integrated as a pluggable plugin with mutual-exclusion loading (swap with the main model on 8GB VRAM), supporting PPT/Word screenshots → Markdown, code screenshots → code blocks, and general images → objective descriptions.
- **Complaint-Aware UX**: When users express dissatisfaction, the system classifies the complaint type, generates an apology, and offers targeted clarification questions (with A/B options) before re-answering — forming a complete detection → apology → clarification → re-answer loop.
- **Desktop Application**: Packaged as a Tauri desktop app with an embedded Python backend (PyInstaller), providing a zero-deployment, privacy-first local AI assistant.

---

## Architecture Overview

```
User Input
    ↓
Knowledge Agent  ──► (Knowledge Base + Web Search + Vision Plugin)
    ↓
Writer Agent      ──► (Content Generation with Skill Tree context)
    ↓
Review Agent      ──► (Quality Scoring + Difficulty Assessment)
    ↓
Judge Agent       ──► (Dual-Threshold Routing Decision)
    ↓                     ↓
    ↓              local_output / cloud_enhance (polish / full_rewrite)
    ↓
Result Agent      ──► (Formatting + Cloud Enhancement + Fallback)
    ↓
Final Output  (+ WebSocket real-time push to frontend)
```

**Design Principles:**
- **Local First**: Maximize local processing to reduce cloud API costs and latency.
- **Graceful Degradation**: A single Agent failure does not break the workflow — partial results are returned with an error summary.
- **Graph First, Engine Second**: Knowledge is represented as graphs (Skill Graph, Capability Graph, Reasoning Graph, Intent Graph); engines are callers that operate on these graphs.

---

## Core Features

### 1. 5-Agent Responsibility Chain Workflow

Five Agents execute in a fixed order, each with a clear responsibility:

| Agent | Role | Key Behavior |
|-------|------|--------------|
| **Knowledge** | Knowledge retrieval + requirement summarization | Queries knowledge base, triggers Web Search for time-sensitive topics, invokes Vision Plugin for image inputs |
| **Writer** | Content generation | Uses Skill Tree context and user profile to generate responses |
| **Review** | Quality scoring + difficulty assessment | Outputs review_score (0-1) and difficulty_threshold (0-1), identifies weak dimensions |
| **Judge** | Routing decision | Dual-threshold matrix decides local vs. cloud, and cloud_mode (none / polish / full_rewrite) |
| **Result** | Formatting + cloud enhancement | Executes cloud enhancement if needed, falls back to Writer output on API failure |

- Real-time status and step details are pushed to the frontend via WebSocket (two channels: `agent_status` for progress, `workflow_step` for details).
- Agent context is passed sequentially through `current_context`.

### 2. Self-Learning Skill Engine

A domain-aware skill management system with a YAML-defined skill tree and automatic patch generation.

- **Skill Tree Domain Detection**: Traverses leaf nodes, matches keywords, and returns the best skill path (e.g., `root → tech → tech.ai → tech.ai.agent`).
- **Two-Level Intent Cache**:
  - L1: Intent → skill path mapping (lightweight, skips domain detection), 200 entries, 300s TTL.
  - L2: Full WorkflowOutput cache (heavyweight, skips the entire workflow), only caches `executed_locally=true` results under 5000 chars.
  - Fingerprint: SHA256(normalized text) first 16 bits; LRU eviction.
- **Skill Learner (Closed Loop)**:
  - Collects Review feedback with confidence ≥ 0.85, records weak dimensions (score < 0.70).
  - Triggers patch generation after ≥ 3 feedback entries in the same domain.
  - Generates constraints, prohibitions, and suggested keywords from aggregated feedback.
  - Semi-automatic: defaults to pending-review patches; high-confidence scenarios can auto-apply with version bump.

### 3. User Profiling & Long-Term Memory

Two subsystems work together to model the user's cognitive state:

**PersonalBrain (7-Dimensional Profile):**
- Dimensions: identity, long-term goals, preferences, expression style, learning stage, abilities, context.
- Persisted to `storage/profiles/{user_id}.json` with thread-safe access.
- Auto-infers user identity from skill nodes (e.g., coding/tech → developer, education/campus → student).
- Injected into Writer Agent prompts via `build_context()`.

**MemoryStore (Long-Term Memory):**
- Stores `MemoryItem` entries with importance, category, source, and access count.
- Capacity: 200 entries; eviction score = `importance*0.6 + recency*0.25 + access_count*0.15`.
- Memories with importance < 0.3 are not stored.
- Cross-sandbox: all sandboxes share the same user's memory.

**MemoryExtractor:**
- Uses the local model (zero cloud cost) to asynchronously extract facts, preferences, goals, and events from conversations.
- Falls back to rule-based keyword extraction if LLM fails.
- Runs asynchronously without blocking the main workflow.

### 4. Hybrid Local-Cloud Inference

The Judge Agent uses a V2.3 dual-threshold decision matrix:

| Difficulty | Review Score | Decision | Cloud Mode |
|------------|--------------|----------|------------|
| < 0.50 | any | local_output | none |
| 0.50 – 0.65 | ≥ 0.70 | local_output | none |
| 0.50 – 0.65 | < 0.70 | cloud_enhance | polish |
| 0.65 – 0.80 | ≥ 0.80 | local_output | none |
| 0.65 – 0.80 | < 0.80 | cloud_enhance | full_rewrite |
| ≥ 0.80 | any | cloud_enhance | full_rewrite |

- **Strong-Signal-Word Correction**: When ≥ 2 complexity signal words are detected, difficulty is boosted to 0.70 to counter LLM underestimation.
- **Weak-Dimension-Aware Routing**: The routing decision considers weak dimensions from Review (accuracy/professional/completeness) to choose between `polish` and `full_rewrite`.
- **Graceful Degradation**: If the DeepSeek API key is not configured, cloud_enhance degrades to local_output. If the cloud API call fails (401/timeout/network), Result Agent preserves the Writer's original output.

### 5. Vision Model Integration

A pluggable vision plugin (not an Agent) used by the Knowledge Agent when `context.images` is non-empty.

- **Mutual-Exclusion Loading**: On 8GB VRAM, the main model (Qwen2.5:7B, 4.7GB) and vision model (MiniCPM-V, 5.5GB) cannot coexist. A process-level lock serializes the full swap cycle: unload main → load vision → recognize → unload vision → reload main.
- **Poll-Based Unload Confirmation**: Instead of a fixed `sleep(1)`, polls Ollama `/api/ps` to confirm the model is fully unloaded (up to 5s), solving unreliable timing for 7B model unloading.
- **Single-Image Sequential**: Processes one image at a time (max 9) to avoid VRAM peak stacking.
- **Output Formatting**:
  - PPT/Word screenshots → Markdown (headings, lists, tables)
  - Code screenshots → code blocks with language tags
  - General images → objective description (no speculation)
- **Separation of Concerns**: The vision model only describes what it sees — it does not reason, infer, or consider user context. That responsibility belongs to the main model.

### 6. Web Search Plugin with Self-Learning Knowledge Base

A pluggable web search tool for time-sensitive topics (food, travel, weather, reviews).

- **Dual Search Engine**: Uses Bing (primary, `cn.bing.com`) and Sogou (fallback) for China mainland accessibility. DuckDuckGo/Google are avoided due to network restrictions.
- **DeepSeek Summarization**: Raw search results are fed to DeepSeek with a system prompt constraining it to "only use search results, no fabrication, output Markdown with source citations [1][2]."
- **Timely Knowledge Base**: Summarized results are persisted to a separate database (TTL=30 days) with `is_stale` marking. Subsequent queries hit the cache directly; expired entries trigger a fresh search.
- **Authoritative vs. Time-Sensitive Separation**: Stable knowledge lives in the main knowledge base; time-sensitive information lives in the timely knowledge base to prevent contamination.

### 7. Complaint Detection & Clarification Mechanism

When users express dissatisfaction, the system forms a complete detection → apology → clarification → re-answer loop.

- **Complaint Classification**: Detects 5 complaint types via 80+ keyword patterns:
  - A. Understanding error ("理解错了", "答非所问")
  - B. Answer error ("弄错了", "信息有误")
  - C. Capability complaint ("怎么这么笨", "太差了")
  - D. Repetition complaint ("不是刚说过吗", "又忘了")
  - E. Explicit redo ("重新回答", "再答一次")
- **Apology Injection**: Generates a type-specific apology prompt appended to the Writer's system prompt, ensuring the re-answer starts with an apology.
- **Clarification Questions**: Generates 3-5 questions (dynamically adjusted by input length), each with two A/B options (system guesses) plus free-text input. Questions are pushed to the frontend via WebSocket popup.
- **Workflow Pause**: The workflow pauses when the clarification popup is open, preventing the system from continuing to output while the user is making selections.

### 8. Multi-Sandbox Isolation

Each sandbox is a physical SQLite database file with independent conversation history and workflow execution records.

- **Dual-Layer Database**: Global DB stores sandbox metadata; per-sandbox DB stores chat messages, workflow executions, and step records.
- **Auto-Creation**: Sandboxes are created automatically when the user sends their first message, named using keywords extracted from the first question (multi-strategy truncation: punctuation > space > "的" > English boundary > fallback).
- **Complete Workflow Audit**: Saves every Agent's input, output, success status, and duration for full execution traceability.
- **Soft Delete + Physical Cleanup**: Mark `is_active=False` for metadata retention, then delete the `.db` file to free storage.

### 9. Multi-Format Export

Industry-standard tools are preferred over hand-written parsers for quality:

| Format | Primary Tool | Fallback |
|--------|-------------|----------|
| DOCX | pandoc (pypandoc-binary, bundled) | python-docx (line-level Markdown parsing) |
| PPTX | marp-cli (smart pagination, code highlighting) | python-pptx (H2-based pagination) |
| Mind Map | markmap-cli (interactive HTML) | pyecharts Tree |
| Markdown | Native | — |

- **Marp Format Conversion**: Removes original `---` separators (which Marp interprets as page breaks, causing blank pages) and inserts page breaks before each H2 heading.
- **Path Traversal Protection**: Rejects filenames containing `..`, `/`, or `\`.

### 10. Graph-Based Cognitive Architecture

A "Graph First, Engine Second" design philosophy with a suite of graph engines:

- **Skill Graph**: Skill relationships and hierarchy.
- **Capability Graph**: Tracks user skill mastery progress, integrated with the user profile.
- **Reasoning Graph**: Reasoning path representation.
- **Intent Graph**: Intent understanding and disambiguation.
- **Cognitive Controller**: The cognitive hub that coordinates the local planner, decomposer, learning engine, and knowledge recommendation engine.
- **Audit & Validation Pipeline**: Knowledge auditor → problem detection → patch generation → patch validator → skill improvement.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14 (App Router), React, TypeScript, Tailwind CSS, Zustand |
| **Desktop** | Tauri 2.x (Rust shell + PyInstaller backend EXE) |
| **Backend** | FastAPI, WebSocket (python-socketio) |
| **Database** | SQLite (per-sandbox isolation + global metadata) |
| **Local LLM** | Ollama — Qwen2.5:7B (main), Qwen2.5:1.5B (memory extractor), MiniCPM-V (vision) |
| **Cloud LLM** | DeepSeek API (deepseek-v4-pro) |
| **Export** | pandoc (DOCX), marp-cli (PPTX), markmap-cli (mind map) |
| **Web Search** | Bing + Sogou (China-accessible) |

---

## Project Structure

```
AgentMatrix/
├── backend/
│   ├── agents/                    # 5 Agents (knowledge, writer, review, judge, result)
│   ├── api/v1/                    # API routers (workflow, agents, chat, sandbox, settings, etc.)
│   ├── core/
│   │   ├── workflow/              # Workflow orchestration
│   │   ├── skill_engine/          # Self-learning skill engine V2
│   │   ├── memory_store/          # Long-term memory + auto-extractor
│   │   ├── personal_brain/        # 7-dimensional user profile
│   │   ├── sandbox/               # Multi-sandbox management
│   │   ├── graphs/                # Skill, Capability, Reasoning, Intent graphs
│   │   ├── engines/               # Cognitive controller, planner, learning engine
│   │   ├── llm/                   # LLM client, vision plugin, web search plugin
│   │   └── export/                # Multi-format converter
│   ├── prompts/
│   │   ├── skills/                # Skill tree YAML definitions
│   │   └── templates/             # Agent system prompts
│   ├── knowledge/                 # Knowledge base + timely knowledge service
│   └── storage/                   # Profiles, memory, sandboxes (runtime data)
├── frontend/
│   ├── src/
│   │   ├── components/            # Chat, AgentChain, TaskStepList, ClarifyNotification, etc.
│   │   ├── stores/                # Zustand stores (workflow, clarify, audit, error)
│   │   ├── services/api/          # API service layer
│   │   └── types/                 # TypeScript type definitions
│   └── src-tauri/                 # Tauri desktop app config + Rust shell
├── docs/                          # Documentation
└── scripts/                       # Utility scripts
```

---

## Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 22+
- **Ollama** with the following models:
  - `qwen2.5:7b` (main model, Q4, ~4.7GB VRAM)
  - `qwen2.5:1.5b` (memory extractor, Q4, ~1.0GB VRAM)
  - `minicpm-v:latest` (vision model, q4_0, ~5.5GB VRAM)
- **GPU**: NVIDIA RTX 4060 (8GB VRAM) or equivalent
- **DeepSeek API Key** (optional, for cloud enhancement — get it at [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys))

### Installation

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### Run in Development Mode

```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open http://localhost:3000 in your browser.

### Build Desktop Application

```bash
# 1. Package backend as EXE
cd backend
pyinstaller agentmatrix.spec --noconfirm

# 2. Build Tauri desktop app
cd frontend
cargo tauri build
```

The installer will be at `frontend/src-tauri/target/release/bundle/nsis/AgentMatrix_0.1.0_x64-setup.exe`.

---

## Configuration

### Backend (.env)

Create `backend/.env` with:

```env
# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Local Models (Ollama)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Cloud Model (DeepSeek) — leave empty to use local-only mode
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-pro

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

> **Note**: The desktop app stores the DeepSeek API key in `%APPDATA%/AgentMatrix/.env`. On first launch, a guided popup prompts the user to enter their key. The key is never exposed to the frontend or committed to version control.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
