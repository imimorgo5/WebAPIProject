from typing import Optional
from pydantic import ConfigDict
from sqlmodel import SQLModel, Field


class ParserState(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: int = Field(default=0)


class Perfume(SQLModel, table=True):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    brand: str
    actual_price: str
    old_price: str
    url: str

class PerfumePatch(SQLModel):
    title: Optional[str] = None
    brand: Optional[str] = None
    actual_price: Optional[str] = None
    old_price: Optional[str] = None
    url: Optional[str] = None
