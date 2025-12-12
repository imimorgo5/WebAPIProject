from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
import asyncio

from app.db.base import get_db, async_session
from app.models.models import Perfume
from app.services.parser import run_perfumes_generator_once
from app.ws.manager import manager
from app.nats.client import nats_client
from app.utils.utils import parse_price_to_float, perfume_to_dict_obj


router = APIRouter()


@router.get("/perfumes", response_model=List[Perfume])
async def list_perfumes(session: AsyncSession = Depends(get_db), brand: Optional[str] = None, only_discounted: bool =
                        Query(False, description="Если true - вернуть только парфюмы со скидкой, иначе - все")):
    if only_discounted:
        q = select(Perfume).where(Perfume.old_price != "").order_by(Perfume.id)
    else:
        q = select(Perfume).order_by(Perfume.id)

    if brand:
        q = q.where(func.lower(Perfume.brand) == brand.lower())

    result = await session.execute(q)
    return result.scalars().all()


@router.get("/perfumes/{perfume_id}", response_model=Perfume)
async def get_perfume(perfume_id: int, session: AsyncSession = Depends(get_db)):
    perfume = await session.get(Perfume, perfume_id)
    if not perfume:
        raise HTTPException(status_code=404, detail="Perfume not found")
    return perfume


@router.post("/perfumes", response_model=Perfume, status_code=201)
async def create_perfume(perfume_in: Perfume, session: AsyncSession = Depends(get_db)):
    perfume = Perfume(title=perfume_in.title, brand=perfume_in.brand, actual_price=perfume_in.actual_price,
                      old_price=perfume_in.old_price, url=perfume_in.url)
    session.add(perfume)
    await session.commit()
    await session.refresh(perfume)

    data = {"event": "perfume_created", "perfume": Perfume.model_validate(perfume).model_dump(), "source": "api"}
    await manager.broadcast(data)
    try:
        await nats_client.publish("perfumes.updates", data)
    except Exception:
        pass
    return perfume


@router.patch("/perfumes/{perfume_id}", response_model=Perfume)
async def patch_perfume(perfume_id: int, patch: Perfume, session: AsyncSession = Depends(get_db)):
    perfume = await session.get(Perfume, perfume_id)
    if not perfume:
        raise HTTPException(status_code=404, detail="Perfume not found")
    old_actual_raw = perfume.actual_price or ""
    if patch.title is not None:
        perfume.title = patch.title
    if patch.brand is not None:
        perfume.brand = patch.brand
    if patch.actual_price is not None:
        perfume.actual_price = patch.actual_price
    if patch.old_price is not None:
        perfume.old_price = patch.old_price
    if patch.url is not None:
        perfume.url = patch.url
    session.add(perfume)
    await session.commit()
    await session.refresh(perfume)

    data = {"event": "perfume_updated", "perfume": Perfume.model_validate(perfume).model_dump(), "source": "api"}
    await manager.broadcast(data)
    try:
        await nats_client.publish("perfumes.updates", data)
    except Exception:
        pass

    new_actual_raw = perfume.actual_price or ""
    if new_actual_raw != old_actual_raw:
        old_num = parse_price_to_float(old_actual_raw)
        new_num = parse_price_to_float(new_actual_raw)
        if old_num is not None and new_num is not None:
            if new_num > old_num:
                price_event = "price_up"
            elif new_num < old_num:
                price_event = "price_down"
            else:
                price_event = None
            if price_event:
                price_data = {"event": price_event, "perfume": perfume_to_dict_obj(perfume), "source": "api"}
                try:
                    await manager.broadcast(price_data)
                except Exception:
                    pass
                try:
                    await nats_client.publish("perfumes.updates", price_data)
                except Exception:
                    pass

    return perfume


@router.delete("/perfumes/{perfume_id}", response_model=Perfume)
async def delete_perfume(perfume_id: int, session: AsyncSession = Depends(get_db)):
    perfume = await session.get(Perfume, perfume_id)
    if not perfume:
        raise HTTPException(status_code=404, detail="Perfume not found")
    await session.delete(perfume)
    await session.commit()

    data = {"event": "perfume_deleted", "perfume": Perfume.model_validate(perfume).model_dump(), "source": "api"}
    await manager.broadcast(data)
    try:
        await nats_client.publish("perfumes.updates", data)
    except Exception:
        pass
    return perfume


@router.post("/tasks/run")
async def run_generator_background():
    async def _run():
        async with async_session() as session:
            await run_perfumes_generator_once(session)

    asyncio.create_task(_run())
    return {"message": "Фоновая задача запущена"}


@router.get("/brands", response_model=List[str])
async def list_brands(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Perfume.brand).distinct().order_by(Perfume.brand))
    brands = result.scalars().all()
    return brands
