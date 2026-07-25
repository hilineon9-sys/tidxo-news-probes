"""
澳門日報 (Macau Daily) 探針
結構：主頁 → meta refresh → 今日日期頁 → 版面列表 → 文章列表
"""
from datetime import datetime
from urllib.parse import urljoin
from probes.base import BaseProbe
from probes.models import Article
from probes.registry import ProbeRegistry


@ProbeRegistry.register
class MacauDailyProbe(BaseProbe):
    """澳門日報新聞探針"""
    
    SOURCE_NAME = "Macau_Daily"
    BASE_URL = "https://www.macaodaily.com/"
    
    # 版面 node 頁面（優先採集）
    SECTIONS = [
        ("澳聞", "node_2.htm"),
        ("中國", "node_4.htm"),
        ("國際", "node_5.htm"),
        ("體育", "node_6.htm"),
        ("財經", "node_7.htm"),
    ]
    
    async def fetch_raw(self) -> str:
        """獲取今日版面頁"""
        import httpx
        import ssl
        from bs4 import BeautifulSoup
        
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=0')
        
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=ctx)
        try:
            # 1. 獲取主頁（有 meta refresh）
            resp = await client.get(self.BASE_URL)
            resp.raise_for_status()
            html = resp.text
            
            # 2. 跟住 meta refresh 去今日日期頁
            soup = BeautifulSoup(html, "lxml")
            meta = soup.select_one('meta[http-equiv="REFRESH" i]')
            if meta and meta.get("content"):
                content = meta["content"]
                if "URL=" in content.upper():
                    url_part = content.split("URL=")[-1].strip()
                    if not url_part.startswith("http"):
                        url_part = urljoin(self.BASE_URL, url_part)
                    resp = await client.get(url_part)
                    resp.raise_for_status()
                    return resp.text
            
            return html
        finally:
            await client.aclose()
    
    def parse(self, raw_data: str) -> list[Article]:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(raw_data, "lxml")
        articles = []
        
        # 找到今日日期基礎路徑
        # 連結格式：content_1923185.htm → 需要組合成完整 URL
        base_url = "https://www.macaodaily.com/html/"
        
        # 查找所有 content 連結（文章）
        content_links = soup.select('a[href*="content_"]')
        
        seen_urls = set()
        for link in content_links:
            try:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                
                if not title or not href or len(title) < 4:
                    continue
                
                # 組合完整 URL
                if not href.startswith("http"):
                    # content_X.htm 可能在子目錄
                    href = urljoin(self.BASE_URL + "html/2026-07/25/", href)
                
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                articles.append(Article(
                    title=title,
                    url=href,
                    source=self.SOURCE_NAME,
                    published=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
                    language="zh"
                ))
            except Exception:
                continue
        
        return articles
