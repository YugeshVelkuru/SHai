# SmartAssist AI

Enterprise-grade conversational AI agent backend built with **Dialogflow CX**, **FastAPI**, **Python**, **SQL**, and **RAG** (Retrieval-Augmented Generation).

## Architecture

```
┌─────────────────┐     webhook      ┌──────────────────────┐
│  Dialogflow CX  │ ───────────────► │  FastAPI Backend     │
│  (Intent/Entity)│ ◄─────────────── │  /api/v1/webhook     │
└─────────────────┘   fulfillment  └──────────┬───────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
              ┌─────▼─────┐            ┌────────▼────────┐          ┌────────▼────────┐
              │ Ticket    │            │ RAG Knowledge   │          │ Analytics       │
              │ Service   │            │ Base + OpenAI   │          │ & Monitoring    │
              └─────┬─────┘            └────────┬────────┘          └────────┬────────┘
                    │                           │                           │
                    └───────────────────────────┼───────────────────────────┘
                                                │
                                        ┌───────▼───────┐
                                        │  SQLite / SQL │
                                        └───────────────┘
```

## Features

- **Dialogflow CX integration** — Intent classification, entity extraction, context handling, fallback recovery
- **Webhook backend** — FastAPI services for ticket tracking, knowledge retrieval, dynamic responses
- **RAG pipeline** — Structured knowledge base with embedding search + LLM generation (OpenAI optional)
- **Analytics** — Interaction logging, drop-off analysis, intent resolution metrics, trend snapshots
- **Cloud Functions** — Deployable GCP wrapper for production webhook hosting

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Optionally set OPENAI_API_KEY for enhanced RAG generation
```

### 3. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API.

### 4. Test the webhook locally

```bash
curl -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "intentInfo": {"displayName": "greeting", "confidence": 0.95},
    "sessionInfo": {"session": "projects/test/sessions/demo-001"},
    "text": "Hello"
  }'
```

### 5. Test RAG knowledge search

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the refund policy?"}'
```

### 6. Track a demo ticket

```bash
curl http://localhost:8000/api/v1/tickets/SA-DEMO0001
```

## Dialogflow CX Setup

1. Create a Dialogflow CX agent in [Google Cloud Console](https://console.cloud.google.com/dialogflow)
2. Import intents from `dialogflow/agent_config.json` or create them manually
3. Enable **Webhook** fulfillment on each intent
4. Set webhook URL to your deployed endpoint: `https://<your-url>/api/v1/webhook`
5. Configure session parameters: `customer_id`, `ticket_number`, `subject`

## Deploy to Google Cloud Functions

```bash
cd cloud_functions
export GCP_PROJECT_ID=your-project-id
bash deploy.sh
```

Copy the deployed URL into your Dialogflow CX webhook settings.

## API Endpoints

| Method | Endpoint                      | Description                    |
| ------ | ----------------------------- | ------------------------------ |
| POST   | `/api/v1/webhook`             | Dialogflow CX webhook          |
| POST   | `/api/v1/tickets`             | Create support ticket          |
| GET    | `/api/v1/tickets/{number}`    | Track ticket status            |
| POST   | `/api/v1/knowledge/ask`       | RAG-powered Q&A                |
| GET    | `/api/v1/analytics/summary`   | Performance metrics            |
| GET    | `/api/v1/analytics/drop-offs` | Conversation drop-off analysis |

## Project Structure

```
SHai/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings
│   ├── api/routes.py        # REST + webhook routes
│   ├── handlers/            # Intent routing logic
│   ├── services/            # RAG, tickets, analytics
│   ├── models/              # SQLAlchemy models
│   └── schemas/             # Pydantic schemas
├── cloud_functions/         # GCP deployment
├── dialogflow/              # Agent configuration
├── knowledge_base/          # Source knowledge articles
└── requirements.txt
```

## Tech Stack

- **Dialogflow CX** — Conversational AI platform
- **FastAPI** — Async Python web framework
- **SQLAlchemy** — SQL ORM (SQLite default, swap to PostgreSQL for production)
- **scikit-learn / OpenAI** — RAG retrieval and generation
- **Google Cloud Functions** — Serverless deployment

## License

Personal project — SmartAssist AI

{
"intentInfo": {
"displayName": "greeting",
"confidence": 0.95
},
"sessionInfo": {
"session": "projects/test/sessions/demo-001"
},
"text": "Hello"
}
