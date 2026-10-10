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
- [Quick Start (Desktop App)](#quick-start-desktop-app)
- [Getting Started (Source Code)](#getting-started-source-code)
- [Configuration](#configuration)
- [License](#license)

---

## Highlights

- **Self-Learning System**: A closed loop where Review Agent feedback is automatically collected, filtered by confidence, and used to generate skill patches that improve the system over time — no manual retraining required.
- **User Profiling**: A 7-dimensional cognitive profile (identity, goals, preferences, abilities, projects, memory, context) that auto-evolves based on conversation history, combined with a long-term memory store that scores and prunes memories by importance, recency, and access frequency. Both the profile and its Capability Graph (per-skill proficiency with evidence and practice counts) are persisted to disk and restored on restart.
- **Hybrid Local-Cloud Inference**: A four-level rule-only decision chain (critical-risk → quality-rescue fallback → difficulty tier → signal-word boost) decides whether a task is handled locally or enhanced by the cloud, with a strong-signal-word correction to counter systematic LLM underestimation of task difficulty. Every decision is recorded with an auditable rationale.
- **Vision Model**: `qwen2.5vl:7b` integrated as a pluggable plugin. Since V4.4 the vision model and the main text model are the **same multimodal model**, so image recognition reuses the resident model with zero swap cost — supporting PPT/Word screenshots → Markdown, code screenshots → code blocks, and general images → objective descriptions.
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
- Persisted to `storage/profiles/{user_id}.json` with thread-safe access (atomic write + `.bak`).
- The same file carries the **Capability Graph** under its `capability` key, so proficiency
  updates are persisted alongside the profile and restored on the next construction.
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

The Judge Agent applies a four-level decision chain. **The levels are evaluated in order — the
first matching level wins**, so a low difficulty does not guarantee local execution.

| Priority | Condition | Decision | Cloud Mode |
|----------|-----------|----------|------------|
| 1 | `risk_level == "critical"` | `cloud_enhance` | `full_rewrite` |
| 2 | `weighted_score < 0.50` | `cloud_enhance` | `full_rewrite` |
| 2b | `weighted_score ∈ [0.50, 0.70)` **and** based on audited self-learned knowledge | `local_output` | `none` |
| 3 | `difficulty < 0.50` | `local_output` | `none` |
| 4 | `difficulty ∈ [0.50, 0.65)` and `weighted_score ≥ 0.70` | `local_output` | `none` |
| 4b | `difficulty ∈ [0.50, 0.65)` and `weighted_score < 0.70` | `cloud_enhance` | `polish_<weakest dimension>` |
| 5 | `difficulty ∈ [0.65, 0.80)` and `weighted_score ≥ 0.80` | `local_output` | `none` |
| 5b | `difficulty ∈ [0.65, 0.80)` and `weighted_score < 0.80` | `cloud_enhance` | `full_rewrite` |
| 6 | `difficulty ≥ 0.80` | `cloud_enhance` | `full_rewrite` |

**Notes on the two thresholds — they act on different variables and must not be conflated:**

- **`difficulty`** (from the Review Agent) selects the tier.
- **`weighted_score`** (the Review Agent's weighted quality score) decides whether the cloud
  path is actually taken. The quality-rescue fallback threshold is `0.50`, relaxed to **`0.40`**
  when the answer is grounded in audited self-learned knowledge (a trust bonus — the system is
  more willing to keep such answers local).
- Because level 2 outranks the difficulty tiers, `difficulty < 0.50` with a low score still
  escalates to the cloud. Lowering the difficulty boundary does **not** reduce cloud usage.

- **Strong-Signal-Word Correction**: When ≥ 2 complexity signal words are detected, difficulty is
  boosted to 0.70 to counter systematic LLM underestimation of task difficulty.
- **Weak-Dimension-Aware Routing**: Within the polish tiers, the cloud mode targets the weakest
  dimension reported by Review (`polish_accuracy`, `polish_completeness`, …).
- **Review weighting**: the rule-engine path scores six dimensions —
  accuracy 0.25, professional 0.20, completeness 0.20, reasoning 0.15, structure 0.10,
  actionable 0.10. Every routing decision writes its rationale into `reason[]` for audit.
- **Graceful Degradation**: Without a DeepSeek API key, every `cloud_enhance` row degrades to
  `local_output`. If the cloud call fails (401 / timeout / network), Result Agent preserves the
  Writer's original output.

### 5. Vision Model Integration

A pluggable vision plugin (not an Agent) used by the Knowledge Agent when `context.images` is non-empty.

- **Single Unified Model (V4.4)**: The vision model and the main text model are the same `qwen2.5vl:7b` (native multimodal). No swap cycle is needed — the model stays resident (`keep_alive=5m`) and recognition requests reuse it directly. This removes the previous 3–5s "unload main → load vision → recognize → unload → reload main" penalty.
- **Single-Image Sequential**: A process-level lock serializes recognition so only one image is processed at a time (max 9), avoiding VRAM peak stacking. The lock now exists for concurrency safety, not for VRAM exclusion.
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

| Graph | Purpose | Persistence | Data status |
|-------|---------|-------------|-------------|
| **Skill Graph** | Skill relationships and hierarchy | `core/graphs/skill_graph.yaml` | **Populated** — 636 nodes / 435 edges |
| **Capability Graph** | Per-skill user proficiency (5 levels) with evidence and practice counts | `storage/profiles/{user_id}.json` → `capability` | Persisted; populated by actual usage |
| **Reasoning Graph** | Reasoning patterns and applicable domains | `core/graphs/reasoning_graph.yaml` | 5 preset patterns; self-learned patterns pending review |
| **Intent Graph** | Session intent timeline (domain, task type, involved skills) | `storage/intents/{user_id}.json` | Persisted; accumulates with real sessions |

- **Capability Graph** is loaded and saved together with the user profile, so proficiency updates
  survive a restart. `GET/PATCH /api/v1/brain/{user_id}/capability` reads and writes it.
- **Intent Graph** records one entry per session and persists immediately (capped at the most
  recent 100). Its `get_consecutive_domain_run()` signal drives soft throttling in
  `knowledge_recommendation.py` — repeated questions in the same domain still get recommended
  content, but at a lower priority.
- **Cognitive Controller**: The cognitive hub that coordinates the local planner, decomposer, learning engine, and knowledge recommendation engine.
- **Audit & Validation Pipeline**: Knowledge auditor → problem detection → patch generation → patch validator → skill improvement.

> The four graphs are at different maturity levels by design: the Skill Graph carries the
> routing signals today, while the other three accumulate data through actual use.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14 (App Router), React, TypeScript, Tailwind CSS, Zustand |
| **Desktop** | Tauri 2.x (Rust shell + PyInstaller backend EXE) |
| **Backend** | FastAPI, WebSocket (python-socketio) |
| **Database** | SQLite (per-sandbox isolation + global metadata) |
| **Local LLM** | Ollama — `qwen2.5vl:7b` (unified multimodal: main text generation + vision), `qwen2.5:1.5b` (lightweight memory extractor) |
| **Cloud LLM** | DeepSeek API — `deepseek-flash` (DeepSeek-V4.1-Flash; API model id is `deepseek-flash`) |
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

## Quick Start (Desktop App)

The easiest way to get started — no Python or Node.js installation required.

> ⚠️ **Installer temporarily unavailable.** The earlier `v0.1.0` installer was built from a much
> older codebase and has been taken down. Until the current version is packaged, follow
> [Getting Started (Source Code)](#getting-started-source-code) to run AgentMatrix from source.

### Step 1: Download the Installer

Download the installer from [GitHub Releases](https://github.com/han1326189481/AgentMatrix/releases)
once a new build is published — there is no downloadable installer right now.

### Step 2: Install Ollama and Models

1. Install [Ollama](https://ollama.com/download) for Windows.
2. Open a terminal and pull the required models:

```bash
# Unified multimodal model — text generation AND image recognition (~6.0GB VRAM)
ollama pull qwen2.5vl:7b

# Lightweight model (memory extraction, ~1.0GB VRAM)
ollama pull qwen2.5:1.5b
```

### Step 3: Install and Launch

1. Run the installer (e.g. `AgentMatrix_<version>_x64-setup.exe`) to install.
2. Launch **AgentMatrix** from the Start Menu or desktop shortcut.
3. On first launch, a splash screen will appear while the backend initializes (this may take 30–90 seconds on first run as PyInstaller extracts the bundle).
4. When prompted, enter your **DeepSeek API Key** (get one at [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)). You can skip this to use local-only mode.

### Step 4: Start Chatting

That's it! The app is ready. Type your question and the 5-Agent workflow will handle the rest.

> **System Requirements**: Windows 10/11 (x64), NVIDIA GPU with 8GB+ VRAM recommended, 16GB RAM.

---

## Getting Started (Source Code)

For developers who want to run from source or contribute to the project.

### Prerequisites

- **Python** 3.13 (verified; 3.10+ required)
- **Node.js** 22+
- **Ollama** with the following models:
  - `qwen2.5vl:7b` (unified multimodal model — main text generation + image recognition, ~6.0GB VRAM)
  - `qwen2.5:1.5b` (memory extractor, Q4, ~1.0GB VRAM)
- **GPU**: NVIDIA RTX 4060 (8GB VRAM) or equivalent
- **DeepSeek API Key** (optional, for cloud enhancement — get it at [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys))
- **Rust + Tauri CLI** (only needed for building the desktop app)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/han1326189481/AgentMatrix.git
cd AgentMatrix

# 2. One-shot environment setup — creates backend/.venv313 (Python 3.13)
#    and installs all backend dependencies (Aliyun mirror)
.\setup.ps1

# 3. Install frontend dependencies
cd frontend
npm install
```

### Run in Development Mode

```powershell
# One-shot: starts Ollama + backend + frontend, each in its own window
.\start_all.ps1

# Check service status only
.\start_all.ps1 -CheckOnly

# Stop everything
.\stop_all.ps1
```

Or manually:

```bash
# Terminal 1 — Backend (must use the venv interpreter and socket_app)
cd backend
.venv313\Scripts\python.exe -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000 --log-level info

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open http://localhost:3000 in your browser.

> **Security defaults (P0)**: the backend binds to 127.0.0.1 only. To expose it on the LAN (e.g. for a demo), set `SERVER_HOST=0.0.0.0` in `backend/.env` — and know what you are doing.

### Build Desktop Application

```bash
# 1. Package backend as EXE (run inside the 3.13 venv)
cd backend
.venv313\Scripts\python.exe -m pip install pyinstaller
.venv313\Scripts\python.exe -m PyInstaller agentmatrix.spec --noconfirm

# 2. Copy the EXE to the backend root
copy dist\agentmatrix-backend.exe .\

# 3. Build Tauri desktop app (requires Rust + Tauri CLI)
cd ../frontend
cargo tauri build
```

The installer will be at `frontend/src-tauri/target/release/bundle/nsis/AgentMatrix_0.1.0_x64-setup.exe`.

---

## Configuration

### Backend (.env)

Create `backend/.env` with:

```env
# Server (127.0.0.1 by default — local only; see P0 security notes)
SERVER_HOST=127.0.0.1
SERVER_PORT=8000

# Local Models (Ollama)
OLLAMA_HOST=http://localhost:11434
# Unified multimodal model — used for both text generation and image recognition
OLLAMA_MODEL=qwen2.5vl:7b
OLLAMA_VISION_MODEL=qwen2.5vl:7b
# Optional per-Agent model override, e.g. "extractor:qwen2.5:1.5b"
# OLLAMA_AGENT_MODELS=

# Cloud Model (DeepSeek) — leave empty to use local-only mode
# Unified cloud model = DeepSeek-V4.1-Flash; its API model id is `deepseek-flash`.
# (The legacy value `deepseek-v4-pro` is deprecated — do not use it.)
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-flash
# Vision fallback on the cloud side uses the same model
DEEPSEEK_VISION_MODEL=deepseek-flash

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
