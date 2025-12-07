import json
from typing import Optional

from nats.aio.client import Client as NATS

from app.config import NATS_SERVERS, NATS_SUBJECT
from app.db.base import async_session
from app.models.models import Perfume
from app.ws.manager import manager
from sqlmodel import select


class NATSClient:
    def __init__(self):
        self._nc: Optional[NATS] = None
        self._sub = None

    async def connect(self, servers: Optional[list[str]] = None):
        servers = servers or NATS_SERVERS
        self._nc = NATS()
        await self._nc.connect(servers=servers)
        self._sub = await self._nc.subscribe(NATS_SUBJECT, cb=self._on_message)

    async def publish(self, subject: str, data: dict):
        if not self._nc or not getattr(self._nc, "is_connected", False):
            return
        try:
            await self._nc.publish(subject, json.dumps(data).encode())
        except Exception:
            pass

    async def _on_message(self, msg):
        try:
            data = json.loads(msg.data.decode())
        except Exception:
            return

        try:
            await manager.broadcast({"event": "nats_message", "payload": data})
        except Exception:
            pass

        source = (data.get("source") or "").lower()

        if source in ("api", "parser"):
            return

        perf = data.get("perfume")
        if not perf:
            return

        url = perf.get("url")
        if not url:
            return

        try:
            async with async_session() as session:
                async with session.begin():
                    result = await session.execute(select(Perfume).where(Perfume.url == url))
                    existing = result.scalars().first()
                    if existing:
                        changed = False
                        if perf.get("title") and perf["title"] != existing.title:
                            existing.title = perf["title"]
                            changed = True
                        if perf.get("brand") and perf["brand"] != existing.brand:
                            existing.brand = perf["brand"]
                            changed = True
                        if perf.get("actual_price") and perf["actual_price"] != existing.actual_price:
                            existing.actual_price = perf["actual_price"]
                            changed = True
                        if perf.get("old_price") is not None and perf["old_price"] != existing.old_price:
                            existing.old_price = perf["old_price"]
                            changed = True
                        if changed:
                            session.add(existing)
                            await session.flush()
                            await session.refresh(existing)
                            await manager.broadcast({"event": "perfume_updated", "perfume": Perfume.model_validate(existing).model_dump()})
                    else:
                        new = Perfume(
                            title=perf.get("title", ""),
                            brand=perf.get("brand", ""),
                            actual_price=perf.get("actual_price", ""),
                            old_price=perf.get("old_price", ""),
                            url=url,
                        )
                        session.add(new)
                        await session.flush()
                        await session.refresh(new)
                        await manager.broadcast({"event": "perfume_created", "perfume": Perfume.model_validate(new).model_dump()})
        except Exception as e:
            print(e)

    async def close(self):
        if self._nc and getattr(self._nc, "is_connected", False):
            try:
                await self._nc.drain()
            except Exception:
                pass
            try:
                await self._nc.close()
            except Exception:
                pass


nats_client = NATSClient()
