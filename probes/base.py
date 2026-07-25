"""
探針基類 — 所有新聞源探針的統一接口
"""
from abc import ABC, abstractmethod
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from .models import Article


class BaseProbe(ABC):
    """探針基類"""
    
    # 子類必須覆蓋
    SOURCE_NAME: str = ""
    BASE_URL: str = ""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.client.aclose()
    
    @abstractmethod
    async def fetch_raw(self) -> str:
        """獲取原始數據（HTML/JSON/XML）"""
        pass
    
    @abstractmethod
    def parse(self, raw_data: str) -> list[Article]:
        """解析原始數據為文章列表"""
        pass
    
    async def fetch(self) -> list[Article]:
        """執行採集流程"""
        try:
            raw = await self.fetch_raw()
            return self.parse(raw)
        except Exception as e:
            raise RuntimeError(f"{self.SOURCE_NAME} probe failed: {e}")
    
    def _get_soup(self, html: str) -> BeautifulSoup:
        """輔助方法：解析 HTML"""
        return BeautifulSoup(html, "lxml")
    
    async def _get_html(self, url: Optional[str] = None) -> str:
        """輔助方法：GET 請求並返回 HTML"""
        target = url or self.BASE_URL
        resp = await self.client.get(target)
        resp.raise_for_status()
        return resp.text
    
    async def _get_json(self, url: Optional[str] = None) -> dict:
        """輔助方法：GET 請求並返回 JSON"""
        target = url or self.BASE_URL
        resp = await self.client.get(target)
        resp.raise_for_status()
        return resp.json()
