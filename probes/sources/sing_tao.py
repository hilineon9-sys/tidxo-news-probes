"""
星島日報 (Sing Tao Daily) 探針
"""
from datetime import datetime
from probes.base import BaseProbe
from probes.models import Article
from probes.registry import ProbeRegistry


@ProbeRegistry.register
class SingTaoProbe(BaseProbe):
    """星島日報新聞探針"""
    
    SOURCE_NAME = "Sing_Tao"
    BASE_URL = "https://www.singtao.ca/"
    
    async def fetch_raw(self) -> str:
        return await self._get_html("https://www.singtao.ca/")
    
    def parse(self, raw_data: str) -> list[Article]:
        soup = self._get_soup(raw_data)
        articles = []
        
        # 星島日報新聞列表結構
        items = soup.select("article, .news-item, .post-item, a[href*='article']")
        
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
                    url = f"https://www.singtao.ca{url}"
                
                # 發佈時間
                time_elem = item.select_one("time, .publish-time, span.date")
                published = None
                if time_elem:
                    time_text = time_elem.get("datetime") or time_elem.get_text(strip=True)
                    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y", "%Y年%m月%d日"]:
                        try:
                            published = datetime.strptime(time_text, fmt)
                            break
                        except ValueError:
                            continue
                
                # 摘要
                summary_elem = item.select_one("p, .summary, .excerpt")
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
