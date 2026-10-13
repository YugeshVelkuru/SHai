from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.database import KnowledgeArticle, Ticket, TicketStatus
from app.services.rag_service import RAGService

KNOWLEDGE_BASE = [
    {
        "title": "Billing Cycle and Payment Methods",
        "category": "billing",
        "content": (
            "Your billing cycle starts on the date of your first subscription. "
            "We accept Visa, Mastercard, American Express, UPI, and net banking. "
            "Invoices are generated on the 1st of each month and payment is due within 15 days. "
            "You can update payment methods in Account Settings > Billing."
        ),
        "keywords": "payment invoice billing cycle credit card upi due date",
    },
    {
        "title": "Refund Policy",
        "category": "billing",
        "content": (
            "Refunds are processed within 5-7 business days for eligible purchases. "
            "Annual subscriptions cancelled within 30 days receive a full refund. "
            "Monthly subscriptions are non-refundable but can be cancelled anytime. "
            "Contact support with your order ID to initiate a refund."
        ),
        "keywords": "refund money back cancel subscription charge",
    },
    {
        "title": "Shipping Times and Tracking",
        "category": "shipping",
        "content": (
            "Standard shipping takes 5-7 business days. Express shipping arrives in 2-3 business days. "
            "You'll receive a tracking number via email once your order ships. "
            "Track packages at our website using your order number or tracking ID."
        ),
        "keywords": "delivery shipping track order express standard",
    },
    {
        "title": "International Shipping",
        "category": "shipping",
        "content": (
            "We ship to 40+ countries. International orders take 10-15 business days. "
            "Customs duties and taxes may apply based on your country. "
            "Free shipping on international orders over $100."
        ),
        "keywords": "international overseas customs duty global",
    },
    {
        "title": "Return and Exchange Policy",
        "category": "returns",
        "content": (
            "Items can be returned within 30 days of delivery in original condition. "
            "Initiate a return from your order history or contact support. "
            "Return shipping is free for defective items. "
            "Exchanges are processed within 3-5 business days of receiving the return."
        ),
        "keywords": "return exchange defective warranty 30 days",
    },
    {
        "title": "Account Password Reset",
        "category": "account",
        "content": (
            "Click 'Forgot Password' on the login page and enter your registered email. "
            "You'll receive a reset link valid for 24 hours. "
            "If you don't receive the email, check spam or contact support. "
            "For security, password must be at least 8 characters with one number."
        ),
        "keywords": "password reset login forgot account security",
    },
    {
        "title": "Account Deactivation",
        "category": "account",
        "content": (
            "To deactivate your account, go to Settings > Privacy > Deactivate Account. "
            "Your data will be retained for 90 days in case you want to reactivate. "
            "After 90 days, all personal data is permanently deleted per our privacy policy."
        ),
        "keywords": "delete account deactivate close privacy gdpr",
    },
    {
        "title": "Premium Support SLA",
        "category": "billing",
        "content": (
            "Premium subscribers receive 24/7 priority support with a 2-hour response SLA. "
            "Critical issues are escalated immediately to senior engineers. "
            "Premium support includes dedicated account manager and quarterly business reviews."
        ),
        "keywords": "premium priority sla support enterprise",
    },
]

SAMPLE_TICKETS = [
    {
        "ticket_number": "SA-DEMO0001",
        "customer_id": "cust_001",
        "subject": "Unable to access premium features",
        "description": "Paid for premium but features still locked.",
        "status": TicketStatus.IN_PROGRESS.value,
        "priority": "high",
    },
    {
        "ticket_number": "SA-DEMO0002",
        "customer_id": "cust_001",
        "subject": "Refund request for duplicate charge",
        "description": "Charged twice for March subscription.",
        "status": TicketStatus.OPEN.value,
        "priority": "medium",
    },
]


async def seed_database() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KnowledgeArticle).limit(1))
        if result.scalar_one_or_none():
            return

        rag = RAGService()
        for item in KNOWLEDGE_BASE:
            article = KnowledgeArticle(**item)
            db.add(article)
        await db.commit()

        result = await db.execute(select(KnowledgeArticle))
        articles = result.scalars().all()
        for article in articles:
            await rag.index_article(db, article)

        for ticket_data in SAMPLE_TICKETS:
            db.add(Ticket(**ticket_data))
        await db.commit()
