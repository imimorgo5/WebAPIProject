import asyncio
from typing import List, Tuple, Optional
from playwright.async_api import async_playwright, Page
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ParserState, Perfume
from app.config import BASE_URL, PARSE_LIMIT, MAX_PAGES
from app.ws.manager import manager
from app.nats.client import nats_client


parse_lock = asyncio.Lock()


def normalize(text: Optional[str]):
    if not text:
        return ""
    return " ".join(text.replace("\u00A0", " ").replace("\xa0", " ").split()).strip()


class LetuParser:
    base_url = BASE_URL

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

    async def load_page(self, url: str):
        if not self.page:
            raise RuntimeError("Parser not started")
        await self.page.goto(url, timeout=60_000)
        await self.page.wait_for_selector("a[href*='/product/']", timeout=10_000)

    async def parse_products_from_page(self):
        if not self.page:
            raise RuntimeError("Parser not started")

        products: List[Perfume] = []
        anchors = await self.page.query_selector_all("a[href*='/product/']")
        for a in anchors:
            try:
                href = await a.get_attribute("href")
                if not href:
                    continue
                link = "https://www.letu.ru" + href

                title_el = await a.query_selector(".product-tile-name__text > span:nth-child(3)")
                title = normalize(await title_el.text_content() if title_el else "")

                brand_el = await a.query_selector(".product-tile-name__text--brand")
                brand = normalize(await brand_el.text_content() if brand_el else "")

                actual_price_el = await a.query_selector(".product-tile-price__text--actual")
                actual_price = normalize(await actual_price_el.text_content() if actual_price_el else "")

                old_price_el = await a.query_selector(".product-tile-price__text--old")
                old_price = normalize(await old_price_el.text_content() if old_price_el else "")

                products.append(Perfume(title=title, brand=brand, actual_price=actual_price, old_price=old_price, url=link))
            except Exception:
                continue
        return products

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


async def parse_site(session: AsyncSession):
    parser = LetuParser()
    await parser.start()
    collected: List[Perfume] = []
    base = parser.base_url.rstrip("/")

    result = await session.execute(select(ParserState).where(ParserState.key == "page"))
    page_state = result.scalars().first()
    if not page_state:
        page_state = ParserState(key="page", value=1)
        session.add(page_state)
        await session.commit()
        await session.refresh(page_state)

    result = await session.execute(select(ParserState).where(ParserState.key == "index"))
    index_state = result.scalars().first()
    if not index_state:
        index_state = ParserState(key="index", value=0)
        session.add(index_state)
        await session.commit()
        await session.refresh(index_state)

    start_page = max(1, page_state.value)
    if start_page > MAX_PAGES:
        start_page = 1
    start_index = max(0, index_state.value)

    page_num = start_page
    page_lengths: dict[int, int] = {}

    next_page = start_page
    next_index = start_index

    while len(collected) < PARSE_LIMIT:
        if page_num > MAX_PAGES:
            page_num = 1

        page_url = f"{base}/page-{page_num}"
        try:
            await parser.load_page(page_url)
        except Exception:
            page_num += 1
            if page_num == start_page:
                break
            continue

        page_products = await parser.parse_products_from_page()
        page_lengths[page_num] = len(page_products)

        if not page_products:
            page_num += 1
            continue

        for i, p in enumerate(page_products):
            if page_num == start_page and i < start_index and len(collected) == 0:
                continue

            if len(collected) >= PARSE_LIMIT:
                break

            collected.append(p)
            next_page = page_num
            next_index = i + 1

        if next_page in page_lengths and next_index >= page_lengths[next_page]:
            next_page = page_num + 1
            next_index = 0

        page_num += 1
        if page_num - start_page > MAX_PAGES + 2:
            break

    await parser.stop()

    if next_page > MAX_PAGES:
        next_page = 1
        next_index = 0

    if not collected:
        next_page = start_page + 1
        next_index = 0
        if next_page > MAX_PAGES:
            next_page = 1

    return collected, next_page, next_index


async def run_perfumes_generator_once(session: AsyncSession):
    async with parse_lock:
        perfumes, next_page, next_index = await parse_site(session)

        result = await session.execute(select(ParserState).where(ParserState.key == "page"))
        page_state = result.scalars().first()
        if page_state:
            page_state.value = next_page
            session.add(page_state)

        result = await session.execute(select(ParserState).where(ParserState.key == "index"))
        index_state = result.scalars().first()
        if index_state:
            index_state.value = next_index
            session.add(index_state)

        if not perfumes:
            await session.commit()
            return 0

        for p in perfumes:
            session.add(p)

        await session.commit()

        result = await session.execute(select(Perfume).order_by(Perfume.id.desc()).limit(len(perfumes)))
        new_perfumes = result.scalars().all()[::-1]
        added = 0
        for perfume in new_perfumes:
            added += 1
            data = {"event": "perfume_created", "perfume": Perfume.model_validate(perfume).model_dump(), "source": "parser"}
            await manager.broadcast(data)
            try:
                await nats_client.publish("perfumes.updates", data)
            except Exception:
                pass

        return added
