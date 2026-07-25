"""
香港電台 (RTHK) 探針 — 使用 RSS Feed
"""
from datetime import datetime
from email.utils import parsedate_to_datetime
import feedparser
from probes.base import BaseProbe
from probes.models import Article
from probes.registry import ProbeRegistry


@ProbeRegistry.register
class RTHKProbe(BaseProbe):
    """香港電台新聞探針（RSS）"""
    
    SOURCE_NAME = "RTHK"
    BASE_URL = "https://rthk.hk/rthk/news/rss/c_expressnews_clocal.xml"
    
    # 可選：多個分類 RSS
    RSS_FEEDS = {
        "local": "https://rthk.hk/rthk/news/rss/c_expressnews_clocal.xml",
        "greater_china": "https://rthk.hk/rthk/news/rss/c_expressnews_greaterchina.xml",
        "international": "https://rthk.hk/rthk/news/rss/c_expressnews_cinternational.xml",
        "finance": "https://rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml",
        "sport": "https://rthk.hk/rthk/news/rss/c_expressnews_csport.xml",
    }
    
    async def fetch_raw(self) -> dict:
        """獲取 RSS feed 並解析"""
        feed = feedparser.parse(self.BASE_URL)
        return {"feed": feed}
    
    def parse(self, raw_data: dict) -> list[Article]:
        feed = raw_data["feed"]
        articles = []
        
        for entry in feed.entries[:30]:
            try:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                
                if not title or not url:
                    continue
                
                # 發佈時間
                published = None
                if "published" in entry:
                    try:
                        published = parsedate_to_datetime(entry.published)
                    except:
                        pass
                
                # 摘要
                summary = entry.get("summary", "").strip()
                if summary:
                    # 去除 HTML tags
                    from bs4 import BeautifulSoup
                    summary = BeautifulSoup(summary, "lxml").get_text(strip=True)
                
                articles.append(Article(
                    title=title,
                    url=url,
                    source=self.SOURCE_NAME,
                    published=published,
                    summary=summary if summary else None,
                    language="zh"
                ))
            except Exception:
                continue
        
        return articles
