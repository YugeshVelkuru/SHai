import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import Ticket, TicketStatus, TicketUpdate
from app.schemas.dialogflow import TicketCreate, TicketResponse


def _generate_ticket_number() -> str:
    return f"SA-{uuid.uuid4().hex[:8].upper()}"


class TicketService:
    """Real-time ticket tracking and management."""

    async def create_ticket(self, db: AsyncSession, data: TicketCreate) -> TicketResponse:
        ticket = Ticket(
            ticket_number=_generate_ticket_number(),
            customer_id=data.customer_id,
            subject=data.subject,
            description=data.description,
            priority=data.priority,
            status=TicketStatus.OPEN.value,
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return TicketResponse.model_validate(ticket)

    async def get_ticket_by_number(
        self, db: AsyncSession, ticket_number: str
    ) -> Ticket | None:
        result = await db.execute(
            select(Ticket)
            .options(selectinload(Ticket.updates))
            .where(Ticket.ticket_number == ticket_number.upper())
        )
        return result.scalar_one_or_none()

    async def get_tickets_by_customer(
        self, db: AsyncSession, customer_id: str
    ) -> list[Ticket]:
        result = await db.execute(
            select(Ticket)
            .where(Ticket.customer_id == customer_id)
            .order_by(Ticket.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        db: AsyncSession,
        ticket_number: str,
        status: str,
        message: str = "",
    ) -> Ticket | None:
        ticket = await self.get_ticket_by_number(db, ticket_number)
        if not ticket:
            return None
        ticket.status = status
        ticket.updated_at = datetime.utcnow()
        if message:
            db.add(TicketUpdate(ticket_id=ticket.id, message=message))
        await db.commit()
        await db.refresh(ticket)
        return ticket

    def format_ticket_status(self, ticket: Ticket) -> str:
        updates_text = ""
        if ticket.updates:
            latest = ticket.updates[-1]
            updates_text = f"\nLatest update: {latest.message}"

        return (
            f"Ticket {ticket.ticket_number}\n"
            f"Subject: {ticket.subject}\n"
            f"Status: {ticket.status.replace('_', ' ').title()}\n"
            f"Priority: {ticket.priority.title()}\n"
            f"Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M')}"
            f"{updates_text}"
        )

    def format_ticket_list(self, tickets: list[Ticket]) -> str:
        if not tickets:
            return "You don't have any support tickets on file."
        lines = ["Here are your recent tickets:\n"]
        for t in tickets[:5]:
            lines.append(
                f"• {t.ticket_number} — {t.subject} "
                f"({t.status.replace('_', ' ').title()})"
            )
        return "\n".join(lines)
