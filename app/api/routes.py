import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.handlers.intent_handlers import IntentHandler
from app.schemas.dialogflow import (
    DialogflowWebhookRequest,
    DialogflowWebhookResponse,
    KnowledgeQuery,
    KnowledgeResult,
    TicketCreate,
    TicketResponse,
    TicketStatusUpdate,
)
from app.services.analytics_service import AnalyticsService
from app.services.rag_service import RAGService
from app.services.ticket_service import TicketService

router = APIRouter()
intent_handler = IntentHandler()
rag_service = RAGService()
ticket_service = TicketService()
analytics_service = AnalyticsService()


def _parse_dialogflow_request(body: dict[str, Any]) -> DialogflowWebhookRequest:
    """Parse raw Dialogflow CX webhook JSON into our schema."""
    intent_info = None
    if "intentInfo" in body:
        info = body["intentInfo"]
        intent_info = {
            "name": info.get("name", ""),
            "display_name": info.get("displayName", info.get("display_name", "")),
            "confidence": float(info.get("confidence", 0)),
        }
    elif "queryResult" in body:
        qr = body["queryResult"]
        intent = qr.get("intent", {})
        intent_info = {
            "name": intent.get("name", ""),
            "display_name": intent.get("displayName", ""),
            "confidence": float(qr.get("intentDetectionConfidence", 0)),
        }

    text = ""
    if "text" in body:
        text = body["text"]
    elif "queryResult" in body:
        text = body["queryResult"].get("queryText", "")

    return DialogflowWebhookRequest(
        detect_intent_response_id=body.get("detectIntentResponseId", ""),
        intent_info=intent_info,
        session_info=body.get("sessionInfo", body.get("session_info", {})),
        page_info=body.get("pageInfo", {}),
        fulfillment_info=body.get("fulfillmentInfo", {}),
        text=text,
        language_code=body.get("languageCode", "en"),
        payload=body.get("payload", {}),
    )


@router.post("/webhook", response_model=DialogflowWebhookResponse)
async def dialogflow_webhook(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> DialogflowWebhookResponse:
    """Primary Dialogflow CX webhook endpoint."""
    request = _parse_dialogflow_request(body)
    return await intent_handler.handle(db, request)


@router.post("/tickets", response_model=TicketResponse)
async def create_ticket(
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    return await ticket_service.create_ticket(db, data)


@router.get("/tickets/{ticket_number}")
async def get_ticket(
    ticket_number: str,
    db: AsyncSession = Depends(get_db),
):
    ticket = await ticket_service.get_ticket_by_number(db, ticket_number)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "ticket": TicketResponse.model_validate(ticket),
        "formatted": ticket_service.format_ticket_status(ticket),
    }


@router.patch("/tickets/{ticket_number}")
async def update_ticket(
    ticket_number: str,
    data: TicketStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    ticket = await ticket_service.update_status(
        db, ticket_number, data.status, data.message
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketResponse.model_validate(ticket)


@router.get("/tickets/customer/{customer_id}")
async def list_customer_tickets(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
):
    tickets = await ticket_service.get_tickets_by_customer(db, customer_id)
    return [TicketResponse.model_validate(t) for t in tickets]


@router.post("/knowledge/search", response_model=list[KnowledgeResult])
async def search_knowledge(
    query: KnowledgeQuery,
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeResult]:
    return await rag_service.retrieve(
        db, query.query, category=query.category, top_k=query.top_k
    )


@router.post("/knowledge/ask")
async def ask_knowledge(
    query: KnowledgeQuery,
    db: AsyncSession = Depends(get_db),
):
    answer, sources = await rag_service.generate_answer(
        db, query.query, category=query.category
    )
    return {"answer": answer, "sources": sources}


@router.get("/analytics/summary")
async def analytics_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_summary(db, days=days)


@router.post("/analytics/snapshot")
async def save_analytics_snapshot(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.save_snapshot(db, days=days)


@router.get("/analytics/drop-offs")
async def drop_off_analysis(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.identify_drop_off_points(db, days=days)


@router.get("/analytics/trends/{metric_name}")
async def metric_trends(
    metric_name: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_metric_trends(db, metric_name, limit=limit)
