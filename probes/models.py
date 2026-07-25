"""
統一數據模型 — 所有探針輸出同一格式
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Article(BaseModel):
    """統一文章模型"""
    title: str
    url: str
    source: str = Field(description="新聞源名稱，如 'RTHK'")
    published: Optional[datetime] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    language: str = Field(default="zh", description="zh / en")
    image_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump()


class ProbeResult(BaseModel):
    """探針執行結果"""
    source: str
    articles: list[Article]
    fetched_at: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None
