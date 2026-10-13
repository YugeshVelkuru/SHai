import json
import math
import re
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import KnowledgeArticle
from app.schemas.dialogflow import KnowledgeResult

settings = get_settings()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _keyword_score(query: str, article: KnowledgeArticle) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    corpus = f"{article.title} {article.keywords} {article.content}".lower()
    article_tokens = _tokenize(corpus)
    overlap = query_tokens & article_tokens
    return len(overlap) / len(query_tokens)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a)
    vb = np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


class RAGService:
    """Retrieval-Augmented Generation pipeline with structured knowledge base."""

    def __init__(self) -> None:
        self._openai_client: Any = None

    @property
    def openai_client(self) -> Any:
        if self._openai_client is None and settings.openai_api_key:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    async def _get_embedding(self, text: str) -> list[float] | None:
        if not self.openai_client:
            return None
        try:
            response = self.openai_client.embeddings.create(
                model=settings.embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception:
            return None

    async def index_article(self, db: AsyncSession, article: KnowledgeArticle) -> None:
        embedding = await self._get_embedding(f"{article.title}\n{article.content}")
        if embedding:
            article.embedding_json = json.dumps(embedding)
            await db.commit()

    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        category: str | None = None,
        top_k: int | None = None,
    ) -> list[KnowledgeResult]:
        top_k = top_k or settings.rag_top_k
        stmt = select(KnowledgeArticle).where(KnowledgeArticle.is_active.is_(True))
        if category:
            stmt = stmt.where(KnowledgeArticle.category == category)
        result = await db.execute(stmt)
        articles = result.scalars().all()

        query_embedding = await self._get_embedding(query)
        scored: list[tuple[KnowledgeArticle, float]] = []

        for article in articles:
            if query_embedding and article.embedding_json:
                article_embedding = json.loads(article.embedding_json)
                score = _cosine_similarity(query_embedding, article_embedding)
            else:
                score = _keyword_score(query, article)
            if score >= settings.rag_similarity_threshold:
                scored.append((article, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            KnowledgeResult(
                title=article.title,
                category=article.category,
                content=article.content,
                score=round(score, 4),
            )
            for article, score in scored[:top_k]
        ]

    async def generate_answer(
        self,
        db: AsyncSession,
        query: str,
        category: str | None = None,
    ) -> tuple[str, list[KnowledgeResult]]:
        results = await self.retrieve(db, query, category=category)
        if not results:
            return (
                "I couldn't find relevant information in our knowledge base. "
                "Would you like me to create a support ticket for you?",
                [],
            )

        context = "\n\n".join(
            f"[{r.category}] {r.title}\n{r.content}" for r in results
        )

        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are SmartAssist AI, a helpful customer support agent. "
                                "Answer using ONLY the provided knowledge base context. "
                                "Be concise, friendly, and accurate. If context is insufficient, say so."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Context:\n{context}\n\nCustomer question: {query}",
                        },
                    ],
                    temperature=0.3,
                    max_tokens=400,
                )
                answer = response.choices[0].message.content or ""
                return answer.strip(), results
            except Exception:
                pass

        # Fallback: template-based response from retrieved chunks
        best = results[0]
        answer = (
            f"Based on our knowledge base ({best.category} — {best.title}):\n\n"
            f"{best.content[:500]}{'...' if len(best.content) > 500 else ''}"
        )
        if len(results) > 1:
            answer += "\n\nRelated topics: " + ", ".join(r.title for r in results[1:])
        return answer, results
