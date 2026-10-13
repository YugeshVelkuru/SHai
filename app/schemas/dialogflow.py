from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DialogflowEntity(BaseModel):
    name: str
    value: str
    original_value: str = ""


class DialogflowIntentInfo(BaseModel):
    name: str
    display_name: str = ""
    confidence: float = 0.0


class DialogflowWebhookRequest(BaseModel):
    """Subset of Dialogflow CX webhook request payload."""

    detect_intent_response_id: str = ""
    intent_info: DialogflowIntentInfo | None = None
    session_info: dict[str, Any] = Field(default_factory=dict)
    page_info: dict[str, Any] = Field(default_factory=dict)
    fulfillment_info: dict[str, Any] = Field(default_factory=dict)
    text: str = ""
    language_code: str = "en"
    payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def session_id(self) -> str:
        return self.session_info.get("session", "unknown")

    @property
    def intent_name(self) -> str:
        if self.intent_info:
            return self.intent_info.display_name or self.intent_info.name
        return "Default Fallback Intent"

    @property
    def intent_confidence(self) -> float:
        if self.intent_info:
            return self.intent_info.confidence
        return 0.0

    @property
    def user_text(self) -> str:
        return self.text or self.payload.get("text", "")


class DialogflowWebhookResponse(BaseModel):
    fulfillment_response: dict[str, Any]
    session_info: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class TicketCreate(BaseModel):
    customer_id: str
    subject: str
    description: str
    priority: str = "medium"


class TicketResponse(BaseModel):
    id: int
    ticket_number: str
    customer_id: str
    subject: str
    description: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketStatusUpdate(BaseModel):
    status: str
    message: str = ""


class KnowledgeQuery(BaseModel):
    query: str
    category: str | None = None
    top_k: int = 3


class KnowledgeResult(BaseModel):
    title: str
    category: str
    content: str
    score: float


class AnalyticsSummary(BaseModel):
    total_interactions: int
    resolved_sessions: int
    drop_off_rate: float
    fallback_rate: float
    avg_response_time_ms: float
    intent_resolution_rate: float
    top_intents: list[dict[str, Any]]
    rag_usage_rate: float
