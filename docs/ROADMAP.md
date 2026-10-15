# DeepInsight OS - Architecture Roadmap

## Pre-Phase 2 Checkpoint: Agent SDK
All agents must inherit from `BaseAgent` which enforces a strict lifecycle:
`initialize -> validate -> gather_context -> execute -> validate_output -> request_approval -> finalize -> audit`.

## New Layer: The Intelligence Layer
**Current Architecture:** Knowledge -> Reporting Agent -> Content -> SEO -> Email
**Future Architecture:** Knowledge -> **Intelligence Layer** -> Agents

The Intelligence Layer is a centralized module ensuring no agent duplicates logic. It acts as the core IP of DeepInsight OS and contains:
1. **Rule Engine:** Deterministic business logic that identifies trends without LLMs (e.g. CTR up + Bounce down = Positive Engagement).
2. **Insight Engine:** Combines Rules + Knowledge to generate insights with a deterministic Confidence Score (0-100).
3. **Evaluation Engine:** Automatically scores outputs based on Groundedness, Completeness, Citation Coverage, Readability, Professional Tone, and Hallucination Risk.

## Phase 3 & Beyond: The Evolution Plan

### 1. Memory Layers Architecture
Memory should scale hierarchically:
`Global Knowledge -> Agency Knowledge -> Client Knowledge -> Campaign Knowledge -> Conversation Memory -> Current Task`

### 2. Entity-Centric Knowledge Graph
The KB will evolve from document-centric to entity-centric:
`Clients -> Brands -> Products -> Campaigns -> Competitors -> People -> Channels -> Documents -> Chunks`

### 3. Prompt Studio
Prompts will move out of the codebase (Git) and into a UI-driven **Prompt Studio** with full version control, rollback, and evaluation, allowing strategists to modify prompts without deploying code.

### 4. Multi-model Routing
Instead of hardcoding a model per task, a Task Router will evaluate the request and dynamically route between Qwen, DeepSeek, Gemma, Llama, and Phi based on cost/performance requirements.

### 5. Hybrid Retrieval
We will upgrade the `Retriever` interface to support Vector Search, BM25, Metadata Filtering, and Recency Ranking.
