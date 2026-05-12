# JARVIS Blueprint — Part 2: Cost, DevOps, AI Engineering, Code & Final Plan

---

# 9. COST OPTIMIZATION

## 9.1 Monthly Cost Breakdown

| Category | Component | MVP Cost | V1 Cost | V2 Cost |
|----------|-----------|----------|---------|---------|
| **LLM API** | GPT-4o-mini | $5 | $5 | $3 |
| **LLM API** | Gemini 1.5 Flash | $2 | $3 | $5 |
| **LLM API** | Embeddings (text-embedding-3-small) | $0.50 | $1 | $1 |
| **Hosting** | VPS (Hetzner CX22) | $4 | $4 | $4 |
| **Hosting** | Domain | $0 (subdomain) | $1 | $1 |
| **Database** | Supabase Free | $0 | $0 | $0 |
| **Email** | SendGrid Free | $0 | $0 | $0 |
| **Monitoring** | Better Stack Free | $0 | $0 | $0 |
| **Monitoring** | LangSmith Free | $0 | $0 | $0 |
| **CI/CD** | GitHub Actions Free | $0 | $0 | $0 |
| **OCR** | PaddleOCR (self-hosted) | $0 | $0 | $0 |
| **Total** | | **~$11.50** | **~$14** | **~$14** |

Assumes ~200 requests/day averaging 1k input + 500 output tokens each.

## 9.2 Cost Reduction Strategies

### LLM Optimization

| Strategy | Savings | Implementation |
|----------|---------|---------------|
| **Caching** | 30-50% | Cache identical LLM responses by input hash (24h TTL) |
| **Model routing** | 40-60% | Simple intents -> Gemini Flash; Complex -> GPT-4o-mini |
| **Prompt compression** | 20-30% | Summarize conversation history to essential context only |
| **Batch processing** | 15-25% | Combine similar requests into one LLM call |
| **Shorter outputs** | 10-20% | Limit max_tokens, prefer structured JSON over prose |
| **Reduced retries** | 5-10% | On failure, use simpler model instead of retrying expensive one |
| **Local models** | 100% | Use Llama 3.2 8B via Ollama for simple, repetitive tasks |

### Cache Strategy

```python
CACHE_RULES = {
    "market_data": {"ttl": 900, "key": "market:{symbol}"},
    "recipe_search": {"ttl": 86400, "key": "recipe:{query_hash}"},
    "llm_response": {"ttl": 3600, "key": "llm:{model}:{prompt_hash}"},
    "nutrition_info": {"ttl": 604800, "key": "nutrition:{food_name}"},
}
```

### Prompt Optimization

```python
# Before optimization (~500 tokens for context):
CONTEXT = f"""User preferences:
- Diet: {user.diet}
- Workout time: {user.workout_time}
- Investment horizon: {user.horizon}
- Risk tolerance: {user.risk_tolerance}
- Preferred cuisines: {user.cuisines}
- Allergies: {user.allergies}
- Budget per week: {user.budget}
- Calorie target: {user.calories}
- Protein target: {user.protein}
- Meal prep preference: {user.meal_prep}
- Cooking skill level: {user.cooking_skill}
"""

# After optimization (~150 tokens):
CONTEXT = f"User: {user.summary()}"
# Where summary() returns a compressed string like:
# "Vegetarian, 2000cal/120g protein, Indian+Italian, Rs2000/week, beginner cook"
```

### Batch Processing

```
Instead of 7 separate LLM calls for 7-day meal plan:
-> 1 LLM call with instruction to generate all 7 days
-> Saves ~85% on input tokens (shared instructions)
-> Saves ~85% on output overhead
```

## 9.3 Self-Hosted Model Options

| Model | Hardware | Quality | Use Case |
|-------|----------|---------|----------|
| **Llama 3.2 8B** (quantized) | 8GB RAM, CPU ~10 t/s | Good | Simple tasks, routing |
| **Mistral 7B** (quantized) | 6GB RAM | Good | Text generation |
| **Phi-3 Mini** | 4GB RAM | Decent | Classification, routing |
| **Qwen 2.5 7B** | 8GB RAM | Very Good | Balanced option |

**Recommendation:** Run **Llama 3.2 8B** via Ollama on the same VPS for classification/routing. Fall back to GPT-4o-mini for complex generation.

---

# 10. DEPLOYMENT + DEVOPS

## 10.1 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 10.2 Docker Compose

```yaml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: jarvis
      POSTGRES_USER: jarvis
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jarvis"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.12
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}

  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      QDRANT_URL: http://qdrant:6333
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
    depends_on:
      postgres: condition: service_healthy
      redis: condition: service_healthy
      qdrant: condition: service_started
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      QDRANT_URL: http://qdrant:6333
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      postgres: condition: service_healthy
      redis: condition: service_healthy
    command: python -m app.worker

  scheduler:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    command: python -m app.scheduler

  telegram-bot:
    build: ./backend
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      API_URL: http://api:8000
    command: python -m app.bot

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

## 10.3 Production Docker Compose (docker-compose.prod.yml)

```yaml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_DB: jarvis
      POSTGRES_USER: jarvis
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - jarvis_net
    deploy:
      resources:
        limits:
          memory: 2G

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - jarvis_net
    deploy:
      resources:
        limits:
          memory: 512M

  qdrant:
    image: qdrant/qdrant:v1.12
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - jarvis_net
    deploy:
      resources:
        limits:
          memory: 1G

  api:
    build: ./backend
    restart: unless-stopped
    expose:
      - "8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      QDRANT_URL: http://qdrant:6333
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      ENVIRONMENT: production
    depends_on: [postgres, redis, qdrant]
    networks:
      - jarvis_net
    deploy:
      resources:
        limits:
          memory: 1G

  worker:
    build: ./backend
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      QDRANT_URL: http://qdrant:6333
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      ENVIRONMENT: production
    command: python -m app.worker
    networks:
      - jarvis_net

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infrastructure/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./infrastructure/nginx/ssl:/etc/nginx/ssl
    depends_on: [api]
    networks:
      - jarvis_net

  frontend:
    build: ./frontend
    restart: unless-stopped
    expose:
      - "3000"
    environment:
      NEXT_PUBLIC_API_URL: https://jarvis.yourdomain.com
    depends_on: [api]
    networks:
      - jarvis_net

networks:
  jarvis_net:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

## 10.4 Environment Variables

```bash
# .env.example

# Database
DATABASE_URL=postgresql+asyncpg://jarvis:password@localhost:5432/jarvis
DB_PASSWORD=changeme

# Redis
REDIS_URL=redis://:password@localhost:6379/0
REDIS_PASSWORD=changeme

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=changeme

# LLM APIs
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...

# Messaging
TELEGRAM_BOT_TOKEN=...
SENDGRID_API_KEY=...
WHATSAPP_API_KEY=...

# Auth
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
JWT_SECRET=...

# Calendar
GOOGLE_CALENDAR_CREDENTIALS=...

# Search
TAVILY_API_KEY=...

# Environment
ENVIRONMENT=development
LOG_LEVEL=info
```

## 10.5 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: jarvis_test
          POSTGRES_USER: jarvis
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
          pip install -r backend/requirements-dev.txt
      - name: Run linting
        run: |
          ruff check backend/
          ruff format --check backend/
      - name: Run type checking
        run: pyright backend/
      - name: Run tests
        run: pytest backend/tests/ -v --cov=app --cov-report=term
        env:
          DATABASE_URL: postgresql+asyncpg://jarvis:test@localhost:5432/jarvis_test
          REDIS_URL: redis://localhost:6379/0
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## 10.6 GitHub Actions Deploy

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  workflow_dispatch:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: docker compose -f docker-compose.prod.yml build
      - name: Push to registry
        run: |
          docker tag jarvis-api ghcr.io/${{ github.repository }}/api:${{ github.sha }}
          docker push ghcr.io/${{ github.repository }}/api:${{ github.sha }}
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/jarvis
            docker compose pull
            docker compose up -d --remove-orphans
            docker system prune -f
```

## 10.7 Monitoring & Logging

```python
# backend/app/core/logging.py
import structlog

def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if ENVIRONMENT == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(LOG_LEVEL)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage:
logger = structlog.get_logger()
logger.info("agent.task.completed",
    agent="meal", task_id="123", duration_ms=1500, tokens_used=450)
```

## 10.8 Secrets Management

```bash
# 1. Local: .env file (gitignored)
# 2. CI/CD: GitHub Secrets
# 3. Production: scp .env.production user@vps:/opt/jarvis/.env
#    or use Docker secrets / 1password CLI
```

---

# 11. SECURITY + PRIVACY

## 11.1 Authentication & Authorization

| Layer | Method | Implementation |
|-------|--------|---------------|
| API Auth | JWT via Supabase Auth | Supabase handles signup, login, session management |
| Bot Auth | Telegram user ID whitelist | Only authorized Telegram user IDs |
| API Keys | Hashed + stored in DB | For programmatic access |
| Rate Limiting | Redis-based token bucket | Per user, per endpoint, per agent |

```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

async def verify_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> User:
    try:
        user = supabase.auth.get_user(credentials.credentials)
        return User(**user.model_dump())
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")
```

## 11.2 Data Encryption

```python
# Data at rest:
# - PostgreSQL: encrypted at disk level
# - Sensitive fields encrypted with pgcrypto:
#   UPDATE users SET api_key = pgp_sym_encrypt('key', 'password');

# Data in transit:
# - All API traffic via HTTPS/TLS
# - Redis with AUTH password
# - PostgreSQL with SSL
# - Internal Docker network (isolated)
```

## 11.3 Prompt Injection Defense

```python
def sanitize_user_input(text: str) -> str:
    patterns = [
        r"ignore\s+(all\s+)?(previous|above|prior)",
        r"system\s+prompt",
        r"you\s+are\s+(now|not)",
        r"forget\s+(everything|all)",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
    return text
```

## 11.4 Tool Permissioning

```python
AGENT_TOOL_PERMISSIONS = {
    "jarvis": ["search_web", "get_calendar_events", "create_calendar_event",
               "send_notification", "schedule_task", "read_memory", "write_memory",
               "get_user_preference", "search_vector", "execute_agent_function"],
    "meal_agent": ["get_inventory", "update_inventory", "search_recipes",
                   "get_nutrition_info", "estimate_cost", "scan_receipt",
                   "lookup_barcode", "read_memory", "write_memory"],
    "fitness_agent": ["get_calendar_availability", "get_workout_history",
                      "generate_workout_plan", "log_workout", "get_streak_data",
                      "suggest_recovery", "read_memory", "write_memory"],
    "finance_agent": ["get_market_data", "search_financial_news", "get_company_info",
                      "get_economic_calendar", "get_currency_rates", "get_index_data",
                      "summarize_article", "read_memory", "write_memory", "search_web"],
}
```

## 11.5 Rate Limiting

```python
from redis import Redis

class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> bool:
        current = self.redis.incr(f"ratelimit:{key}")
        if current == 1:
            self.redis.expire(f"ratelimit:{key}", window_seconds)
        return current <= max_requests

# Per-user limits:
# - Chat: 30 messages/minute
# - Agent tasks: 10 tasks/minute
# - LLM requests: 20 requests/minute
```

---

# 12. AI ENGINEERING DETAILS

## 12.1 System Prompt Structure

```
1. ROLE DEFINITION (who the agent is)
2. CORE PRINCIPLES (how to behave)
3. CAPABILITIES (what tools/agents available)
4. CONSTRAINTS (limits, rules, disclaimers)
5. CONTEXT (user info, memory, state)
6. TASK (what to do)
7. OUTPUT FORMAT (structured schema)
8. EXAMPLES (few-shot if needed)
```

## 12.2 Agent Planning Loop

```python
async def agent_planning_loop(task: str, tools: list, max_steps: int = 10) -> dict:

    # Step 1: PLAN
    plan = await llm.call(
        system="You are a planner. Break this task into steps.",
        user=f"Task: {task}\nAvailable tools: {[t.name for t in tools]}",
        response_model=PlanSchema,
    )

    results = []
    for step_idx, step in enumerate(plan.steps[:max_steps]):
        # Step 2: EXECUTE
        if step.tool_needed:
            tool = get_tool(step.tool_name)
            tool_result = await tool.run(**step.tool_params)
        else:
            tool_result = None

        result = await llm.call(
            system=SYSTEM_PROMPT,
            user=f"Step {step_idx + 1}: {step.description}\nTool result: {tool_result}",
            response_model=StepResultSchema,
        )
        results.append(result)

        # Step 3: REFLECT (every 3 steps)
        if (step_idx + 1) % 3 == 0:
            reflection = await llm.call(
                system="Review progress so far. Are you on track?",
                user=f"Plan: {plan}\nResults: {results}",
            )
            if reflection.needs_correction:
                plan = await llm.call(
                    system="Revise the remaining plan.",
                    user=f"Remaining: {plan.steps[step_idx+1:]}\nReflection: {reflection}",
                    response_model=PlanSchema,
                )

    # Step 4: SYNTHESIZE
    final = await llm.call(
        system="Synthesize all results into the final output.",
        user=f"Task: {task}\nResults: {results}",
        response_model=task.output_schema,
    )
    return final
```

## 12.3 Tool Calling Architecture

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class Tool(ABC):
    name: str
    description: str
    parameters: dict

    @abstractmethod
    async def run(self, **kwargs):
        pass

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

class SearchWebTool(Tool):
    name = "search_web"
    description = "Search the web for current information"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }
    async def run(self, query: str, max_results: int = 5) -> list[dict]:
        # Implementation using Tavily or SerpAPI
        ...

class GetMarketDataTool(Tool):
    name = "get_market_data"
    description = "Get current market data for stock symbols"
    parameters = {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array", "items": {"type": "string"},
                "description": "Stock symbols (e.g., ['RELIANCE.NS', 'AAPL'])",
            },
        },
        "required": ["symbols"],
    }
    async def run(self, symbols: list[str]) -> list[dict]:
        # Implementation using yfinance
        ...
```

## 12.4 Structured Outputs with Pydantic

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class IntentType(str, Enum):
    QUERY = "query"
    DELEGATE = "delegate"
    SCHEDULE = "schedule"
    COMMAND = "command"

class AgentType(str, Enum):
    MEAL = "meal"
    FITNESS = "fitness"
    FINANCE = "finance"
    NONE = "none"

class JarvisOutput(BaseModel):
    thought: str = Field(description="Step-by-step reasoning")
    intent: IntentType
    target_agent: Optional[AgentType] = None
    task: Optional[str] = None
    response: str = Field(description="Response to the user")
    memory_updates: list[str] = Field(default_factory=list)
    notifications: list[dict] = Field(default_factory=list)

class MealPlanOutput(BaseModel):
    days: list[MealDay]
    grocery_list: list[GroceryItem]
    prep_schedule: list[PrepTask]
    nutrition_summary: dict
    estimated_cost: float

class MealDay(BaseModel):
    day: str
    breakfast: str
    lunch: str
    dinner: str
    snacks: list[str]
    total_calories: int
    total_protein_g: int

class GroceryItem(BaseModel):
    name: str
    category: str
    quantity: float
    unit: str
    estimated_price: float
```

## 12.5 RAG Architecture

```mermaid
graph TD
    Q[Query] --> QC[Query Classifier]
    QC -->|Factual| VL[Vector Lookup - Qdrant]
    QC -->|Time-based| TL[Time Lookup - PostgreSQL]
    QC -->|Preference| PL[Preference Lookup - PostgreSQL]

    VL --> VE[Embed Query - text-embedding-3-small]
    VE --> VS[Vector Search - Qdrant]
    VS --> RR[Re-ranker]

    TL --> TQ[Time-range Query - PostgreSQL]
    TQ --> RR

    PL --> PQ[Preference Query - PostgreSQL]
    PQ --> RR

    RR --> CW[Context Window Assembler]
    CW --> LLM[LLM]

    subgraph Filters
        F1[User ID Filter]
        F2[Time Range Filter]
        F3[Type Filter]
        F4[Relevance Score > 0.7]
    end
    VS --> F1 --> F2 --> F3 --> F4 --> RR
```

## 12.6 Hybrid Search

```python
async def hybrid_search(query: str, user_id: str, collection: str,
                        limit: int = 10, alpha: float = 0.5) -> list[dict]:
    # 1. Generate embedding
    query_embedding = await embed_text(query)

    # 2. Vector search
    vector_results = await qdrant.search(
        collection_name=collection,
        query_vector=query_embedding,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="user_id",
                   match=models.MatchValue(value=user_id))],
        ),
        limit=limit * 2, with_payload=True,
    )

    # 3. Keyword search (PostgreSQL FTS)
    keyword_results = await pg.fetch_all(
        """SELECT * FROM episodic_memory
        WHERE user_id = $1
        AND to_tsvector('english', content) @@ plainto_tsquery('english', $2)
        ORDER BY ts_rank(...) DESC LIMIT $3""",
        user_id, query, limit * 2,
    )

    # 4. Reciprocal Rank Fusion
    return merge_rrf(vector_results, keyword_results, alpha=alpha)

def merge_rrf(vector_results, keyword_results, alpha=0.5, k=60):
    scores = {}
    for rank, result in enumerate(vector_results):
        scores[result.id] = scores.get(result.id, 0) + alpha * (1 / (k + rank + 1))
    for rank, result in enumerate(keyword_results):
        scores[result["id"]] = scores.get(result["id"], 0) + (1 - alpha) * (1 / (k + rank + 1))
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

## 12.7 LangGraph Orchestration Example

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional

class AgentState(TypedDict):
    messages: list
    user_id: str
    intent: Optional[str]
    target_agent: Optional[str]
    task: Optional[str]
    memory_updates: list
    next: Optional[str]

class JarvisGraph:
    def __init__(self, llm, memory, tools):
        self.llm = llm
        self.memory = memory
        self.tools = tools
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("classify_intent", self.classify_intent)
        builder.add_node("load_context", self.load_context)
        builder.add_node("route_to_agent", self.route_to_agent)
        builder.add_node("direct_response", self.direct_response)
        builder.add_node("synthesize", self.synthesize)
        builder.add_node("update_memory", self.update_memory)

        builder.set_entry_point("load_context")
        builder.add_edge("load_context", "classify_intent")
        builder.add_conditional_edges(
            "classify_intent", self.decide_route,
            {"agent": "route_to_agent", "direct": "direct_response"},
        )
        builder.add_edge("route_to_agent", "synthesize")
        builder.add_edge("direct_response", "synthesize")
        builder.add_edge("synthesize", "update_memory")
        builder.add_edge("update_memory", END)
        return builder.compile()

    async def classify_intent(self, state: AgentState):
        response = await self.llm.call(
            system=JARVIS_SYSTEM_PROMPT,
            user=state["messages"][-1]["content"],
            response_model=JarvisOutput,
        )
        return {
            "intent": response.intent.value,
            "target_agent": response.target_agent.value if response.target_agent else None,
            "task": response.task,
            "memory_updates": response.memory_updates,
            "messages": state["messages"] + [{"role": "assistant", "content": response.response}],
        }

    async def route_to_agent(self, state: AgentState):
        agent_map = {"meal": self.meal_agent, "fitness": self.fitness_agent, "finance": self.finance_agent}
        agent = agent_map.get(state["target_agent"])
        if agent:
            return {"agent_result": await agent.process(state["task"])}
        return {}

    def decide_route(self, state: AgentState):
        if state["target_agent"] and state["target_agent"] != "none":
            return "agent"
        return "direct"
```

## 12.8 Multi-Model Routing

```python
class ModelRouter:
    MODEL_TIERS = {
        "complex": {"model": "gpt-4o-mini",
                     "cost_per_1k_input": 0.00015,
                     "suitability": ["planning", "reasoning", "complex_generation"]},
        "medium": {"model": "gemini-1.5-flash",
                    "cost_per_1k_input": 0.000075,
                    "suitability": ["classification", "summarization", "structured_output"]},
        "simple": {"model": "llama-3.2-8b",  # Self-hosted via Ollama
                    "cost_per_1k_input": 0.0,
                    "suitability": ["routing", "extraction", "simple_qa"]},
    }

    async def route(self, task: dict) -> str:
        score = self._assess_complexity(task)
        if score > 0.7: return "complex"
        elif score > 0.3: return "medium"
        else: return "simple"

    def _assess_complexity(self, task: dict) -> float:
        score = 0.0
        if len(task.get("input", "")) > 1000: score += 0.2
        if task.get("requires_tools"): score += 0.3
        if task.get("requires_planning"): score += 0.3
        if task.get("task_type") == "classification": score -= 0.2
        return min(max(score, 0.0), 1.0)
```

## 12.9 Hallucination Mitigation

```python
class HallucinationDetector:
    async def check_hallucination(self, output: str, context: str) -> dict:
        prompt = f"""Given this context: {context}
        And this response: {output}
        Identify claims NOT supported by the context.
        Return as JSON: {{"unsupported_claims": [...], "is_hallucinating": bool}}"""

        result = await self.llm.call(prompt=prompt, response_model=HallucinationCheck)

        if result.is_hallucinating:
            confidence = await self.llm.call(
                prompt=f"Rate confidence (0-100) this response is accurate:\n{output}"
            )
            if confidence < 70:
                output = await self.regenerate_with_facts(output, context)

        return {"is_hallucinating": result.is_hallucinating,
                "mitigation_applied": result.is_hallucinating}
```

## 12.10 Evaluation Framework

```python
class AgentEvaluator:
    METRICS = {
        "task_completion_rate": "Percentage of tasks completed successfully",
        "avg_response_time": "Average time to complete a task",
        "token_efficiency": "Tokens used per completed task",
        "cost_per_task": "USD cost per completed task",
        "user_satisfaction": "Thumbs up/down ratio",
        "tool_call_success_rate": "Percentage of successful tool calls",
        "hallucination_rate": "Detected hallucinations per 100 responses",
    }

    async def evaluate_task(self, task_id: str) -> dict:
        task = await get_task(task_id)
        return {
            "completed": task.status == "completed",
            "duration_ms": (task.completed_at - task.started_at).total_seconds() * 1000,
            "tokens_used": task.token_usage,
            "cost": task.cost_usd,
            "retries": task.retry_count,
            "tool_errors": sum(1 for tc in task.tool_calls if tc.error),
        }
```

---

# 13. UI/UX

## 13.1 Suggested Screens

| Screen | Description | Priority |
|--------|-------------|----------|
| **Chat** | Main interface with Jarvis conversation | P0 |
| **Dashboard** | Overview: upcoming meals, workouts, market summary | P0 |
| **Meal Plans** | Weekly meal plan view with recipes | P1 |
| **Grocery List** | Current grocery list with checkboxes | P1 |
| **Workout Log** | Workout history, streaks, progress charts | P1 |
| **Finance Brief** | Daily market summary, watchlist, newsletter archive | P1 |
| **Settings** | Preferences, notification config, connected accounts | P1 |
| **Analytics** | Token usage, costs, agent performance | P2 |

## 13.2 Navigation Map

```
Home / Dashboard
+-- Chat (main interface)
+-- Meals
|   +-- Weekly Plan
|   +-- Grocery List
|   +-- Inventory
+-- Fitness
|   +-- This Week
|   +-- Workout History
|   +-- Progress
+-- Finance
|   +-- Market Brief
|   +-- Watchlist
|   +-- Newsletter Archive
+-- Settings
|   +-- Profile
|   +-- Preferences
|   +-- Connected Accounts
|   +-- Notifications
+-- Analytics
    +-- Usage
    +-- Costs
    +-- Agent Status
```

## 13.3 Tech Stack for Frontend

| Component | Choice | Why |
|-----------|--------|-----|
| **Framework** | Next.js 14+ | SSR, App Router, API routes |
| **Styling** | Tailwind CSS | Utility-first, rapid development |
| **UI Library** | shadcn/ui | Copy-paste components, Radix-based |
| **State** | React Context + TanStack Query | Server state management |
| **Charts** | Recharts | React-native charting, lightweight |
| **Auth** | Supabase Auth SDK | Direct Supabase integration |

---

# 14. CODEBASE STRUCTURE

## 14.1 Monorepo Structure

```
jarvis/
+-- README.md
+-- docker-compose.yml
+-- docker-compose.prod.yml
+-- .env.example
+-- .gitignore
+-- .github/workflows/
|   +-- ci.yml
|   +-- deploy.yml
+-- backend/
|   +-- Dockerfile
|   +-- requirements.txt
|   +-- requirements-dev.txt
|   +-- pyproject.toml
|   +-- alembic.ini
|   +-- migrations/
|   |   +-- env.py
|   |   +-- versions/
|   +-- app/
|   |   +-- __init__.py
|   |   +-- main.py                 # FastAPI app entry
|   |   +-- config.py               # Settings from env
|   |   +-- core/
|   |   |   +-- auth.py             # JWT/Supabase auth
|   |   |   +-- logging.py          # Structured logging
|   |   |   +-- rate_limit.py       # Rate limiter
|   |   |   +-- cache.py            # Redis cache
|   |   |   +-- dependencies.py     # FastAPI dependencies
|   |   +-- db/
|   |   |   +-- session.py          # DB session management
|   |   |   +-- models.py           # SQLAlchemy models
|   |   |   +-- repositories/       # Data access layer
|   |   |       +-- user_repo.py
|   |   |       +-- conversation_repo.py
|   |   |       +-- task_repo.py
|   |   |       +-- meal_repo.py
|   |   |       +-- fitness_repo.py
|   |   |       +-- finance_repo.py
|   |   +-- memory/
|   |   |   +-- manager.py          # Memory manager
|   |   |   +-- long_term.py        # PostgreSQL memory
|   |   |   +-- vector.py           # Qdrant memory
|   |   |   +-- working.py          # Redis memory
|   |   |   +-- embedding.py        # Embedding service
|   |   +-- agents/
|   |   |   +-- base.py             # Base agent class
|   |   |   +-- jarvis.py           # Jarvis orchestrator
|   |   |   +-- jarvis_graph.py     # LangGraph definition
|   |   |   +-- meal_agent.py       # Meal planner
|   |   |   +-- fitness_agent.py    # Fitness agent
|   |   |   +-- finance_agent.py    # Finance agent
|   |   +-- tools/
|   |   |   +-- registry.py         # Tool registry
|   |   |   +-- web_search.py
|   |   |   +-- market_data.py
|   |   |   +-- calendar.py
|   |   |   +-- notifications.py
|   |   |   +-- ocr_service.py
|   |   +-- api/
|   |   |   +-- router.py
|   |   |   +-- v1/
|   |   |   |   +-- chat.py
|   |   |   |   +-- meals.py
|   |   |   |   +-- fitness.py
|   |   |   |   +-- finance.py
|   |   |   |   +-- memory.py
|   |   |   |   +-- admin.py
|   |   |   +-- websocket.py
|   |   +-- services/
|   |   |   +-- llm.py              # LLM client
|   |   |   +-- notification.py     # Notification service
|   |   |   +-- scheduler.py        # Task scheduler
|   |   |   +-- queue.py            # Queue service
|   |   |   +-- email.py            # Email service
|   |   +-- integrations/
|   |   |   +-- telegram.py
|   |   |   +-- whatsapp.py
|   |   |   +-- calendar.py
|   |   |   +-- supabase.py
|   |   +-- schemas/
|   |   |   +-- chat.py
|   |   |   +-- meal.py
|   |   |   +-- fitness.py
|   |   |   +-- finance.py
|   |   +-- worker.py
|   +-- tests/
|   |   +-- test_agents/
|   |   +-- test_api/
|   |   +-- test_memory/
|   |   +-- test_tools/
|   +-- scripts/
|       +-- seed_data.py
|       +-- test_agents.py
+-- frontend/
|   +-- Dockerfile
|   +-- package.json
|   +-- next.config.js
|   +-- tailwind.config.ts
|   +-- src/
|       +-- app/           # Next.js App Router pages
|       +-- components/    # React components
|       +-- lib/           # Utilities
|       +-- types/         # TypeScript types
|       +-- public/
+-- infrastructure/
|   +-- nginx/nginx.conf
|   +-- monitoring/
|   +-- scripts/
|       +-- setup.sh
|       +-- backup.sh
|       +-- deploy.sh
+-- docs/
|   +-- architecture.md
|   +-- api.md
|   +-- deployment.md
+-- shared/
    +-- types/
    +-- constants/
```

## 14.2 Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Python files | snake_case | `meal_agent.py` |
| Python classes | PascalCase | `MealAgent` |
| Python functions/vars | snake_case | `generate_meal_plan()` |
| TypeScript files | camelCase | `chatWindow.tsx` |
| React components | PascalCase | `ChatWindow.tsx` |
| API endpoints | kebab-case | `/api/v1/meal-plans` |
| Database tables | snake_case | `meal_plans` |
| Database columns | snake_case | `meal_plan_id` |
| Env variables | UPPER_SNAKE | `DATABASE_URL` |
| Git branches | kebab-case | `feature/meal-agent` |

## 14.3 API Conventions

```python
BASE_URL = "/api/v1"

# RESTful endpoints follow: /resource or /resource/{id}
POST   /chat                    # Send message to Jarvis
GET    /chat/conversations      # List conversations
GET    /chat/{id}               # Get conversation

GET    /meals/plans             # List meal plans
POST   /meals/plans             # Generate new plan
GET    /meals/grocery-list      # Get current grocery list
POST   /meals/inventory         # Update inventory

GET    /fitness/workouts        # List workouts
POST   /fitness/workouts        # Log workout
POST   /fitness/plan            # Generate workout plan
GET    /fitness/streaks         # Get streak data

GET    /finance/brief           # Get latest market brief
POST   /finance/brief           # Generate market brief
GET    /finance/watchlist       # Get watchlist
POST   /finance/watchlist       # Add to watchlist

# Response format:
{
    "success": true,
    "data": { ... },
    "error": null,
    "meta": {"page": 1, "limit": 20, "total": 100}
}

# Error format:
{
    "success": false,
    "data": null,
    "error": {"code": "INVALID_INPUT", "message": "Invalid input"}
}
```

---

# 15. EXAMPLE CODE

## 15.1 FastAPI Application Entry

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logging import setup_logging
from app.core.config import settings
from app.api.router import api_router
from app.db.session import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="Jarvis API", version="1.0.0", lifespan=lifespan,
              docs_url="/docs" if settings.ENVIRONMENT == "development" else None)

app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
```

## 15.2 Configuration

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    DATABASE_URL: str = "postgresql+asyncpg://jarvis:password@localhost:5432/jarvis"
    REDIS_URL: str = "redis://:password@localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    SENDGRID_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    TAVILY_API_KEY: str = ""
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    ALLOWED_HOSTS: List[str] = ["localhost", "jarvis.yourdomain.com"]

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

## 15.3 LLM Client

```python
# backend/app/services/llm.py
from openai import AsyncOpenAI
import google.generativeai as genai
from typing import Optional, Type
from pydantic import BaseModel

class LLMClient:
    def __init__(self):
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini = genai.GenerativeModel("gemini-1.5-flash")

    async def call(self, system: str, user: str, model: str = "gpt-4o-mini",
                   response_model: Optional[Type[BaseModel]] = None,
                   temperature: float = 0.7, max_tokens: int = 2048,
                   tools: Optional[list] = None):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        if model.startswith("gpt"):
            kwargs = {"model": model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens}
            if response_model:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": response_model.__name__,
                                    "schema": response_model.model_json_schema()}
                }
            if tools:
                kwargs["tools"] = tools
            response = await self.openai.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if response_model:
                return response_model.model_validate_json(content)
            return content

        elif model.startswith("gemini"):
            prompt = f"{system}\n\n{user}"
            response = await self.gemini.generate_content_async(prompt)
            content = response.text
            if response_model:
                return response_model.model_validate_json(content)
            return content
```

## 15.4 Notification Service

```python
# backend/app/services/notification.py
import aiohttp
from app.core.config import settings

class NotificationService:
    def __init__(self):
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN
        self.sendgrid_key = settings.SENDGRID_API_KEY

    async def send_telegram(self, chat_id: str, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "chat_id": chat_id, "text": text, "parse_mode": "Markdown"
            }) as resp:
                return resp.status == 200

    async def send_email(self, to: str, subject: str, html: str) -> bool:
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {"Authorization": f"Bearer {self.sendgrid_key}",
                   "Content-Type": "application/json"}
        data = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": "jarvis@yourdomain.com"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                return resp.status == 202

    async def notify(self, channel: str, recipient: str,
                     title: str, body: str) -> bool:
        if channel == "telegram":
            return await self.send_telegram(recipient, f"*{title}*\n\n{body}")
        elif channel == "email":
            return await self.send_email(recipient, title, body)
        return False
```

## 15.5 Telegram Bot

```python
# backend/app/integrations/telegram.py
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

class JarvisTelegramBot:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.app = Application.builder().token(token).build()

    async def handle_message(self, update: Update, context):
        user_id = update.effective_user.id
        text = update.message.text

        # Call Jarvis API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_url}/api/v1/chat",
                json={"user_id": str(user_id), "message": text}
            ) as resp:
                result = await resp.json()

        await update.message.reply_text(result["data"]["response"])

    def run(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                            self.handle_message))
        self.app.run_polling()
```

## 15.6 Queue Worker

```python
# backend/app/worker.py
import asyncio
import json
from redis import Redis
from app.core.config import settings

class QueueWorker:
    def __init__(self):
        self.redis = Redis.from_url(settings.REDIS_URL)
        self.handlers = {
            "meal.plan.requested": self.handle_meal_plan,
            "fitness.workout.requested": self.handle_fitness_workout,
            "finance.brief.requested": self.handle_finance_brief,
            "notify.send": self.handle_notification,
        }

    async def process_queue(self, queue_name: str):
        while True:
            _, task_data = self.redis.brpop(queue_name, timeout=5)
            if task_data:
                task = json.loads(task_data)
                handler = self.handlers.get(task["type"])
                if handler:
                    try:
                        await handler(task["payload"])
                        self.redis.set(f"done:{task['idempotency_key']}", "1", ex=86400)
                    except Exception as e:
                        retry_count = task.get("retry_count", 0)
                        if retry_count < 3:
                            task["retry_count"] = retry_count + 1
                            self.redis.lpush("agent_tasks", json.dumps(task))
                        else:
                            self.redis.lpush("dead_letter", json.dumps(task))

    async def run(self):
        queues = ["high_priority", "agent_tasks", "notifications", "background"]
        await asyncio.gather(*[self.process_queue(q) for q in queues])
```

## 15.7 Docker Compose (quick reference)

```yaml
# docker-compose.yml (MVP - minimal services)
version: '3.9'
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: jarvis
      POSTGRES_USER: jarvis
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports: ["6379:6379"]

  qdrant:
    image: qdrant/qdrant:v1.12
    volumes:
      - qdrant_data:/qdrant/storage
    ports: ["6333:6333"]

  api:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${DB_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      QDRANT_URL: http://qdrant:6333
      QDRANT_API_KEY: ${QDRANT_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
    depends_on: [postgres, redis, qdrant]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

---

# 16. FINAL RECOMMENDATION

## 16.1 Recommended Final Stack

| Layer | Component | Monthly Cost |
|-------|-----------|-------------|
| **LLM Orchestrator** | GPT-4o-mini | ~$3-8 |
| **LLM Sub-agents** | Gemini 1.5 Flash | ~$1-3 |
| **LLM Local (optional)** | Llama 3.2 8B via Ollama | $0 |
| **Backend** | FastAPI | $0 |
| **Database** | Supabase (PostgreSQL + Auth) | $0 |
| **Vector DB** | Qdrant (self-hosted Docker) | $0 |
| **Cache/Queue** | Redis (self-hosted Docker) | $0 |
| **Frontend** | Next.js 14 + Tailwind + shadcn/ui | $0 |
| **Hosting** | Hetzner CX22 VPS (~euro 3.99/mo) | ~$4 |
| **Total** | | **~$8-15/month** |

**Why this stack:** It provides the best balance of cost (under $20/month), capability (multi-agent orchestration with memory), and solo-developer-friendliness (Docker Compose deployment, well-documented frameworks).

## 16.2 Simplest MVP Architecture

```mermaid
graph LR
    User -->|Telegram| Bot[Telegram Bot]
    Bot --> API[FastAPI]
    API --> Jarvis[Single Agent<br/>(no LangGraph yet)]
    Jarvis --> Meal[Meal Functions]
    Jarvis --> Fit[Fitness Functions]
    Jarvis --> PG[(PostgreSQL)]
    Jarvis --> LLM[GPT-4o-mini API]
```

- Single process, no queue, no event bus
- Direct function calls instead of LangGraph
- PostgreSQL for everything (no Qdrant/Redis initially)
- Telegram-only interface
- **Build time: 30 days**

## 16.3 Scalable Enterprise Architecture

```mermaid
graph TB
    LB[Load Balancer] --> API1[FastAPI Instance 1]
    LB --> API2[FastAPI Instance 2]
    API1 --> Q[Kafka/RabbitMQ Queue]
    API2 --> Q
    Q --> W1[Worker 1]
    Q --> W2[Worker 2]
    Q --> W3[Worker 3]
    W1 --> PG[(PostgreSQL<br/>Read Replica)]
    W1 --> PG_M[(PostgreSQL<br/>Primary)]
    W1 --> QD[Qdrant Cluster]
    W1 --> RD[(Redis Cluster)]
```

Evolution steps:
1. Replace Docker Compose with Kubernetes (k3s)
2. Add read replicas for PostgreSQL
3. Cluster Qdrant for vector scale
4. Replace Redis pub/sub with Kafka for event durability
5. Add GPU nodes for self-hosted LLMs
6. Add monitoring stack (Prometheus + Grafana + Loki)
7. Multi-tenant support with proper isolation

## 16.4 Exact 30-Day Build Plan

| Day | Tasks |
|-----|-------|
| **1** | Initialize monorepo, Docker Compose, Python project structure |
| **2** | Set up CI/CD (GitHub Actions), linting, type checking |
| **3** | FastAPI app with health check, config, logging |
| **4** | Supabase project, database schema (migrations) |
| **5** | SQLAlchemy models + repositories |
| **6** | LLM client (OpenAI + Gemini), basic tool framework |
| **7** | LangGraph state graph setup |
| **8** | Jarvis intent classification + task routing |
| **9** | Memory manager: conversation history, user preferences |
| **10** | Meal Agent: prompt design, meal plan generation |
| **11** | Meal Agent: grocery list, inventory management |
| **12** | Fitness Agent: workout plan generation |
| **13** | Fitness Agent: scheduling + calendar lookup |
| **14** | Jarvis integration with both agents |
| **15** | Telegram bot setup + message handling |
| **16** | Bot -> API integration, async processing |
| **17** | Notifications, reminders, command handlers |
| **18** | End-to-end meal plan workflow testing |
| **19** | End-to-end fitness workflow testing |
| **20** | Error handling, retry logic, edge cases |
| **21** | Hetzner VPS setup, Docker deployment |
| **22** | Nginx reverse proxy, SSL via Let's Encrypt |
| **23** | Environment config, secrets management |
| **24** | Monitoring (Better Stack), error tracking |
| **25** | LLM caching, token usage tracking |
| **26** | Cost optimization, model routing |
| **27** | Usage documentation, API docs |
| **28** | Final integration testing |
| **29** | Bug fixes, polish |
| **30** | MVP launch |

## 16.5 Exact 90-Day Build Plan

| Week | Phase | Focus |
|------|-------|-------|
| **1-4** | MVP | Core Jarvis + Meal + Fitness + Telegram (30 days) |
| **5** | V1 | Finance Agent: market data APIs, watchlists |
| **6** | V1 | Qdrant setup, vector memory pipeline |
| **7** | V1 | Next.js web dashboard with chat + overview |
| **8** | V1 | Notifications (email + WhatsApp), Celery scheduling |
| **9** | V2 | OCR pipeline (PaddleOCR for receipt scanning) |
| **10** | V2 | Memory optimization (pruning, summarization, RAG) |
| **11** | V2 | Voice input (speech-to-text), mobile-responsive UI |
| **12** | V2 | Evaluation, monitoring, cost analytics dashboard |

## 16.6 Future Hiring Plan

| Role | When | Why |
|------|------|-----|
| **Backend AI Engineer** | Month 3+ | Scale agents, improve RAG, optimize costs |
| **Frontend Engineer** | Month 3+ | Build production web UI, mobile app |
| **ML Engineer** | Month 6+ | Fine-tune models, knowledge graphs |
| **DevOps Engineer** | Month 6+ | Kubernetes, multi-tenant infrastructure |
| **Product Manager** | Month 9+ | User research, feature prioritization |

## 16.7 Open Source Repositories to Study

| Repository | Why Study It |
|------------|-------------|
| **langchain-ai/langgraph** | Core orchestration framework |
| **run-llama/llama_index** | RAG patterns, memory management |
| **pydantic/pydantic-ai** | Type-safe agent framework |
| **livekit/agents** | Voice agent architecture (for voice roadmap) |
| **n8n-io/n8n** | Visual workflow patterns |
| **supabase/supabase** | Backend-as-a-service reference |
| **mlflow/mlflow** | AI evaluation and tracking (for agent eval) |
| **openai/openai-cookbook** | Prompt engineering patterns |
| **qdrant/qdrant** | Vector search reference implementation |

## 16.8 Learning Resources

| Topic | Resource |
|-------|----------|
| **LangGraph** | LangChain Academy (free), LangGraph documentation |
| **FastAPI** | FastAPI official docs + Tiangolo's blog |
| **Next.js** | Next.js Learn tutorial (interactive) |
| **Docker** | Docker's "Getting Started" tutorial |
| **Supabase** | Supabase docs + YouTube channel |
| **AI Engineering** | Lilian Weng's blog (OpenAI), Chip Huyen's "Building LLM Apps" |
| **System Design** | "Designing Data-Intensive Applications" by Martin Kleppmann |
| **Agent Patterns** | Anthropic's "Building Effective Agents" guide |
| **Prompt Engineering** | OpenAI's prompt engineering guide, Anthropic's prompting docs |

## 16.9 Additional Topics Covered

### WhatsApp Integration
- Use **Meta Cloud API** (free for business messaging)
- Webhook receiver in FastAPI to handle incoming messages
- Outgoing via POST to `https://graph.facebook.com/v22.0/{phone_number_id}/messages`
- Requires Facebook Business Verification for production

### Telegram Bot Architecture
- Long polling (MVP) vs Webhook (production)
- State machine per user for multi-step conversations
- Rate limit: 30 messages/second, queue if exceeded

### Voice Assistant Roadmap
- Speech-to-Text: Whisper API ($0.006/min) or faster-whisper (self-hosted)
- Text-to-Speech: OpenAI TTS ($0.015/1k chars) or Piper (self-hosted)
- Voice activity detection (VAD) for chunking
- Phase 1: Send voice -> transcribe -> process -> text reply
- Phase 2: Send voice -> transcribe -> process -> voice reply

### Event Sourcing Possibilities
- All state changes stored as events in PostgreSQL
- Enables replay, audit trails, time-travel debugging
- Event store table: `event_store(id, aggregate_type, aggregate_id, event_type, data, version, created_at)`
- Not needed for MVP -- adds significant complexity

### Knowledge Graph Possibilities
- Extract entities and relationships from conversations
- Store in Neo4j (self-hosted Docker) or as triples in PostgreSQL
- Enables: "What does the user prefer for breakfast?" queries
- Phase 3 feature -- unnecessary for MVP

### Personal Data Ownership
- All data stored on user's VPS or Supabase instance
- No data sent to third parties except LLM APIs (which don't train on API data with proper accounts)
- Full export: `pg_dump + qdrant snapshot`
- Full delete: drop database + delete collections
- GDPR-compliant by design (single-user system)

### Testing Strategy

| Test Type | Scope | Framework |
|-----------|-------|-----------|
| **Unit tests** | Individual functions, tools, schemas | pytest |
| **Integration tests** | API endpoints, database, Redis | pytest + httpx |
| **Agent tests** | LLM output structure, tool selection | pytest + mocks |
| **E2E tests** | Full workflows (meal plan -> grocery list) | pytest + docker |
| **Load tests** | Queue throughput, API response times | locust |

### Monitoring KPIs

| KPI | Target | Alert If |
|-----|--------|----------|
| Task completion rate | > 95% | < 90% |
| Average response time | < 5s | > 15s |
| Token cost per day | < $0.50 | > $1.00 |
| Tool call success rate | > 98% | < 95% |
| Error rate | < 1% | > 5% |
| User satisfaction | > 80% | < 60% |

### Token Usage Optimization

```python
# Track tokens per agent, per user, per day
TOKEN_BUDGETS = {
    "daily_limit": 100000,  # total tokens per day
    "agent_limits": {
        "jarvis": 40000,
        "meal": 20000,
        "fitness": 20000,
        "finance": 20000,
    },
    "model_costs": {
        "gpt-4o-mini": {"input": 0.00000015, "output": 0.00000060},
        "gemini-1.5-flash": {"input": 0.000000075, "output": 0.00000030},
    }
}
```

---

## 16.10 Final Words

This blueprint is designed to be **built by one engineer** in **30 days to MVP** and **90 days to full production**.

Key success factors:
1. **Start simple** -- Telegram bot only, no queue, no event bus
2. **Add complexity only when needed** -- Don't over-engineer
3. **Monitor costs from day one** -- Track every token
4. **Ship fast, iterate** -- MVP is the goal, not perfection
5. **Use existing services** -- Supabase, SendGrid, etc. Don't build infrastructure

The system is designed to grow with you:
- Cost: $0/month (local) -> $15/month (VPS) -> $100/month (scaled)
- Users: 1 (personal) -> 5 (family) -> 50 (small team)
- Agents: 3 -> 10+ (extensible architecture)
- Complexity: Monolith -> Microservices -> Orchestrated

**Start building.**
