"""
無綫新聞 (TVB News) 探針
"""
from datetime import datetime
from probes.base import BaseProbe
from probes.models import Article
from probes.registry import ProbeRegistry


@ProbeRegistry.register
class TVBNewsProbe(BaseProbe):
    """無綫新聞探針"""
    
    SOURCE_NAME = "TVB_News"
    BASE_URL = "https://inews.tvb.com/"
    
    async def fetch_raw(self) -> str:
        # TVB 新聞主頁
        return await self._get_html("https://inews.tvb.com/")
    
    def parse(self, raw_data: str) -> list[Article]:
        soup = self._get_soup(raw_data)
        articles = []
        
        # TVB 新聞列表結構（根據實際 HTML 調整）
        # 常見結構：div.news-item, article, .latest-news
        items = soup.select("article, div.news-item, .news-list li, a[href*='/article/']")
        
        for item in items[:20]:
            try:
                # 標題和連結
                title_elem = item.select_one("h2 a, h3 a, .title a, a")
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = title_elem.get("href", "")
                
                if not title or not url:
                    continue
                
                if not url.startswith("http"):
                    url = f"https://inews.tvb.com{url}"
                
                # 發佈時間
                time_elem = item.select_one("time, .publish-time, span.date")
                published = None
                if time_elem:
                    time_text = time_elem.get("datetime") or time_elem.get_text(strip=True)
                    # 嘗試解析日期
                    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%Y年%m月%d日"]:
                        try:
                            published = datetime.strptime(time_text, fmt)
                            break
                        except ValueError:
                            continue
                
                # 摘要
                summary_elem = item.select_one("p.summary, .description, .intro")
                summary = summary_elem.get_text(strip=True) if summary_elem else None
                
                # 圖片
                img_elem = item.select_one("img")
                image_url = img_elem.get("src") if img_elem else None
                
                articles.append(Article(
                    title=title,
                    url=url,
                    source=self.SOURCE_NAME,
                    published=published,
                    summary=summary,
                    language="zh",
                    image_url=image_url
                ))
            except Exception:
                continue
        
        return articles
