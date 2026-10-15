# DeepInsight OS - Project Rules

These rules are strict, non-negotiable, and apply to **all** phases of the DeepInsight OS project.

## Rule 1: Never Couple AI to the Application
Everything AI-related must sit behind robust interfaces. No business logic should ever know which underlying model is being used. 

`Application -> AI Service -> LLM Provider Interface -> [Ollama, OpenAI, Qwen, DeepSeek]`

## Rule 2: Everything is Tenant-Aware
Every single operation must include `client_id`. No shortcuts.
- Every database table (where applicable)
- Every query
- Every API endpoint
- Every cache entry
- Every vector in the store

## Rule 3: Uniform Interface Usage
Every future agent must use the exact same interfaces for interacting with the Knowledge Base.
- `Retriever`
- `VectorStore`
- `EmbeddingProvider`
- `KnowledgeService`
- `DocumentLoader`
No agent is permitted to bypass these and directly access infrastructure (e.g., pgvector).

## Rule 4: Every Agent is Stateless
Agents do not maintain state. All long-term memory, context, and state are stored strictly within the Knowledge Base.

## Rule 5: Build Observability Early
Every AI call must log extensively. Future debugging requires:
- Agent Name
- Start Time
- End Time
- Duration
- Tokens Used
- Cost (even if $0)
- Prompt Version
- Model Version
- Retrieved Chunks
- Confidence Score
- Errors

## Rule 6: Every Module is Replaceable
Nothing should depend directly on `pgvector`, `Ollama`, `BGE`, or `Qwen`. Code depends strictly on abstract interfaces.

## Rule 7: Extensive Documentation
Every phase must generate and maintain:
- Architecture Diagram
- ER Diagram
- Flow Diagram
- API Docs
- Sequence Diagram
- README
- Decision Log
