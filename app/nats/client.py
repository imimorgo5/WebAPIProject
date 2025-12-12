import json
from typing import Optional

from nats.aio.client import Client as NATS

from app.config import NATS_SERVERS, NATS_SUBJECT
from app.db.base import async_session
from app.models.models import Perfume
from app.ws.manager import manager
from sqlmodel import select
from app.utils.utils import parse_price_to_float, perfume_to_dict_obj


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

        source = (data.get("source") or "").lower()
        if source in ("api", "parser", "nats_server"):
            return

        perf = data.get("perfume")
        if not perf or not isinstance(perf, dict):
            return

        required_fields = {"title", "brand", "actual_price", "old_price", "url"}
        if not required_fields.issubset(set(perf.keys())):
            return

        url = perf.get("url")
        if not url:
            return

        try:
            async with async_session() as session:
                async with session.begin():
                    result = await session.execute(select(Perfume).where(Perfume.url == url))
                    existing = result.scalars().first()

                    price_event = None

                    if existing:
                        changed = False
                        old_actual_raw = existing.actual_price or ""
                        new_actual_raw = perf.get("actual_price") or ""

                        if perf.get("title") and perf["title"] != (existing.title or ""):
                            existing.title = perf["title"]
                            changed = True
                        if perf.get("brand") and perf["brand"] != (existing.brand or ""):
                            existing.brand = perf["brand"]
                            changed = True
                        if perf.get("old_price") is not None and perf["old_price"] != (existing.old_price or ""):
                            existing.old_price = perf["old_price"]
                            changed = True
                        if perf.get("actual_price") and perf["actual_price"] != (existing.actual_price or ""):
                            old_num = parse_price_to_float(old_actual_raw)
                            new_num = parse_price_to_float(new_actual_raw)
                            if old_num is not None and new_num is not None:
                                if new_num > old_num:
                                    price_event = "price_up"
                                elif new_num < old_num:
                                    price_event = "price_down"
                            existing.actual_price = perf["actual_price"]
                            changed = True

                        if changed:
                            session.add(existing)
                            await session.flush()
                            await session.refresh(existing)

                            payload = {
                                "event": "perfume_updated",
                                "perfume": perfume_to_dict_obj(existing),
                                "source": "nats_server",
                            }
                            try:
                                await manager.broadcast(payload)
                            except Exception:
                                pass
                            try:
                                await self.publish(NATS_SUBJECT, payload)
                            except Exception:
                                pass

                            if price_event:
                                ppayload = {
                                    "event": price_event,
                                    "perfume": perfume_to_dict_obj(existing),
                                    "source": "nats_server",
                                }
                                try:
                                    await manager.broadcast(ppayload)
                                except Exception:
                                    pass
                                try:
                                    await self.publish(NATS_SUBJECT, ppayload)
                                except Exception:
                                    pass

                    else:
                        new = Perfume(
                            title=perf.get("title", "") or "",
                            brand=perf.get("brand", "") or "",
                            actual_price=perf.get("actual_price", "") or "",
                            old_price=perf.get("old_price", "") or "",
                            url=url,
                        )
                        session.add(new)
                        await session.flush()
                        await session.refresh(new)

                        payload = {
                            "event": "perfume_created",
                            "perfume": perfume_to_dict_obj(new),
                            "source": "nats_server",
                        }
                        try:
                            await manager.broadcast(payload)
                        except Exception:
                            pass
                        try:
                            await self.publish(NATS_SUBJECT, payload)
                        except Exception:
                            pass

        except Exception as e:
            print("Error in NATS _on_message:", e)

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
