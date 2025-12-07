from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel

from app.config import DATABASE_URL

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)