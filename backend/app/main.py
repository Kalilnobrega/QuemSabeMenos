import os
import time

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.events import Pong

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=CORS_ORIGINS)

api = FastAPI(title="Quem Sabe Menos?")
api.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@sio.event
async def ping_server(sid: str) -> dict:
    return Pong(server_time=time.time()).model_dump()


app = socketio.ASGIApp(sio, other_asgi_app=api)
