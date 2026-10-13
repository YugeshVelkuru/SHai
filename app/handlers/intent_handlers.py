import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dialogflow import (
    DialogflowWebhookRequest,
    DialogflowWebhookResponse,
    TicketCreate,
)
from app.services.analytics_service import AnalyticsService
from app.services.rag_service import RAGService
from app.services.ticket_service import TicketService

rag_service = RAGService()
ticket_service = TicketService()
analytics_service = AnalyticsService()


def _text_response(text: str, **session_params: Any) -> DialogflowWebhookResponse:
    return DialogflowWebhookResponse(
        fulfillment_response={
            "messages": [{"text": {"text": [text]}}],
        },
        session_info={"parameters": session_params} if session_params else {},
    )


def _extract_entities(request: DialogflowWebhookRequest) -> dict[str, str]:
    params = request.session_info.get("parameters", {})
    entities: dict[str, str] = {}
    for key, value in params.items():
        if value is not None and value != "":
            if isinstance(value, dict):
                entities[key] = str(value.get("original", value))
            else:
                entities[key] = str(value)
    return entities


class IntentHandler:
    """Route Dialogflow CX intents to backend services."""

    INTENT_HANDLERS = {
        "track.ticket": "handle_track_ticket",
        "create.ticket": "handle_create_ticket",
        "list.tickets": "handle_list_tickets",
        "knowledge.search": "handle_knowledge_search",
        "faq.billing": "handle_faq",
        "faq.shipping": "handle_faq",
        "faq.returns": "handle_faq",
        "faq.account": "handle_faq",
        "greeting": "handle_greeting",
        "goodbye": "handle_goodbye",
        "agent.escalation": "handle_escalation",
    }

    async def handle(
        self, db: AsyncSession, request: DialogflowWebhookRequest
    ) -> DialogflowWebhookResponse:
        start = time.perf_counter()
        intent = request.intent_name
        entities = _extract_entities(request)
        user_text = request.user_text
        is_fallback = intent in ("Default Fallback Intent", "Default Welcome Intent") or (
            request.intent_confidence < 0.5 and intent not in self.INTENT_HANDLERS
        )

        if is_fallback or intent not in self.INTENT_HANDLERS:
            response = await self.handle_fallback(db, request, entities)
            fallback = True
        else:
            handler_name = self.INTENT_HANDLERS[intent]
            handler = getattr(self, handler_name)
            response = await handler(db, request, entities)
            fallback = False

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        bot_text = ""
        messages = response.fulfillment_response.get("messages", [])
        if messages and "text" in messages[0]:
            bot_text = messages[0]["text"]["text"][0]

        await analytics_service.log_interaction(
            db=db,
            session_id=request.session_id,
            intent=intent,
            confidence=request.intent_confidence,
            user_utterance=user_text,
            bot_response=bot_text,
            entities=entities,
            used_rag=response.payload.get("used_rag", False),
            fallback_triggered=fallback,
            response_time_ms=elapsed_ms,
        )
        return response

    async def handle_greeting(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        return _text_response(
            "Hello! I'm SmartAssist AI, your customer support assistant. "
            "I can help you track tickets, answer questions, or create a new support request. "
            "How can I help you today?"
        )

    async def handle_goodbye(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        await analytics_service.mark_session_resolved(db, request.session_id)
        return _text_response(
            "Thank you for contacting us! Have a great day. "
            "Feel free to reach out anytime you need assistance."
        )

    async def handle_track_ticket(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        ticket_number = entities.get("ticket_number", "")
        if not ticket_number:
            return _text_response(
                "Please provide your ticket number (e.g., SA-ABC12345) so I can look it up."
            )
        ticket = await ticket_service.get_ticket_by_number(db, ticket_number)
        if not ticket:
            return _text_response(
                f"I couldn't find ticket {ticket_number.upper()}. "
                "Please double-check the number or create a new ticket."
            )
        return _text_response(ticket_service.format_ticket_status(ticket))

    async def handle_create_ticket(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        customer_id = entities.get("customer_id", "anonymous")
        subject = entities.get("subject", "")
        description = entities.get("description", request.user_text)

        if not subject:
            return _text_response(
                "What would you like the subject of your support ticket to be?",
                awaiting_ticket_subject=True,
            )

        ticket = await ticket_service.create_ticket(
            db,
            TicketCreate(
                customer_id=customer_id,
                subject=subject,
                description=description,
            ),
        )
        return _text_response(
            f"I've created support ticket {ticket.ticket_number} for you.\n"
            f"Subject: {ticket.subject}\n"
            f"Status: Open\n\n"
            "Our team will review it shortly. You can ask me to track this ticket anytime."
        )

    async def handle_list_tickets(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        customer_id = entities.get("customer_id", "anonymous")
        tickets = await ticket_service.get_tickets_by_customer(db, customer_id)
        return _text_response(ticket_service.format_ticket_list(tickets))

    async def handle_knowledge_search(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        query = entities.get("search_query", request.user_text)
        category = entities.get("category")
        answer, results = await rag_service.generate_answer(db, query, category=category)
        response = _text_response(answer)
        response.payload = {"used_rag": True, "sources": [r.title for r in results]}
        return response

    async def handle_faq(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        category_map = {
            "faq.billing": "billing",
            "faq.shipping": "shipping",
            "faq.returns": "returns",
            "faq.account": "account",
        }
        category = category_map.get(request.intent_name, None)
        answer, results = await rag_service.generate_answer(
            db, request.user_text, category=category
        )
        response = _text_response(answer)
        response.payload = {"used_rag": True, "sources": [r.title for r in results]}
        return response

    async def handle_escalation(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        return _text_response(
            "I'm connecting you with a human agent. "
            "Please hold — average wait time is 3 minutes.\n\n"
            "In the meantime, would you like me to create a priority support ticket?"
        )

    async def handle_fallback(
        self, db: AsyncSession, request: DialogflowWebhookRequest, entities: dict
    ) -> DialogflowWebhookResponse:
        """Fallback recovery: attempt RAG retrieval before generic response."""
        answer, results = await rag_service.generate_answer(db, request.user_text)
        if results:
            response = _text_response(
                f"I think this might help:\n\n{answer}\n\n"
                "Was this helpful? You can also ask to speak with an agent."
            )
            response.payload = {"used_rag": True, "fallback_recovery": True}
            return response

        return _text_response(
            "I'm not sure I understood that. Here are things I can help with:\n"
            "• Track or create a support ticket\n"
            "• Answer billing, shipping, or returns questions\n"
            "• Connect you with a human agent\n\n"
            "Could you rephrase your question?"
        )
