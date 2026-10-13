import functions_framework
from flask import Request

from app.main import app as fastapi_app


@functions_framework.http
def smartassist_webhook(request: Request):
    """Google Cloud Function entry point for Dialogflow CX webhooks."""
    import asyncio

    from httpx import ASGITransport, AsyncClient

    async def _handle():
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            method = request.method
            path = request.path or "/api/v1/webhook"
            headers = {k: v for k, v in request.headers if k.lower() != "host"}
            body = request.get_data()

            response = await client.request(
                method=method,
                url=path,
                headers=headers,
                content=body,
            )
            return response.status_code, response.headers, response.content

    status, headers, content = asyncio.run(_handle())

    excluded = {"transfer-encoding", "content-encoding", "content-length"}
    response_headers = {
        k: v for k, v in headers.items() if k.lower() not in excluded
    }
    return content, status, response_headers
