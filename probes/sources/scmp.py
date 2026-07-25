"""
南華早報 (South China Morning Post) 探針
"""
from datetime import datetime
from probes.base import BaseProbe
from probes.models import Article
from probes.registry import ProbeRegistry


@ProbeRegistry.register
class SCMPProbe(BaseProbe):
    """南華早報新聞探針"""
    
    SOURCE_NAME = "SCMP"
    BASE_URL = "https://www.scmp.com/rss/2/feed"
    
    async def fetch_raw(self) -> dict:
        import feedparser
        feed = feedparser.parse(self.BASE_URL)
        return {"feed": feed}
    
    def parse(self, raw_data: dict) -> list[Article]:
        from email.utils import parsedate_to_datetime
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
                    from bs4 import BeautifulSoup
                    summary = BeautifulSoup(summary, "lxml").get_text(strip=True)
                
                articles.append(Article(
                    title=title,
                    url=url,
                    source=self.SOURCE_NAME,
                    published=published,
                    summary=summary if summary else None,
                    language="en"
                ))
            except Exception:
                continue
        
        return articles
