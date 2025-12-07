from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.tasks.fetcher import start_background, stop_background
from app.db.base import init_db
from app.ws.manager import manager
from app.nats.client import nats_client


app = FastAPI(title="Perfumes API", version="1.0")

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/perfumes")
async def ws_perfumes(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(data)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)


@app.on_event("startup")
async def on_startup():
    await init_db()
    try:
        await nats_client.connect()
    except Exception:
        pass
    await start_background()


@app.on_event("shutdown")
async def on_shutdown():
    await stop_background()
    try:
        await nats_client.close()
    except Exception:
        pass
