# Tidxo 資訊探針採集模組

高兼容性新聞採集框架，每個新聞源只需實現 `fetch_raw()` + `parse()` 兩個方法。

## 架構特點

- **統一基類**：所有探針繼承 `BaseProbe`
- **統一數據模型**：Pydantic `Article`，所有源輸出同一格式
- **自動註冊**：新探針放入 `sources/` 自動發現
- **配置驅動**：每個源嘅 URL、選擇器放 class 變量

## 已支援新聞源

| 源 | 狀態 | 語言 | 方式 |
|---|---|---|---|
| RTHK 香港電台 | ✅ | 粵/中 | RSS |
| SCMP 南華早報 | ✅ | 英 | RSS |
| 澳門日報 | ✅ | 中 | HTML |
| TVB 無綫新聞 | 🔧 | 中 | - |
| 星島日報 | 🔧 | 中 | HTML |

## 快速開始

```bash
pip install -r requirements.txt
python -m probes.runner
```

## 添加新新聞源

```python
from probes.base import BaseProbe
from probes.models import Article
from probes.registry import ProbeRegistry

@ProbeRegistry.register
class MyProbe(BaseProbe):
    SOURCE_NAME = "My_Source"
    BASE_URL = "https://example.com/news"
    
    async def fetch_raw(self) -> str:
        return await self._get_html()
    
    def parse(self, raw_data: str) -> list[Article]:
        soup = self._get_soup(raw_data)
        articles = []
        # 解析邏輯...
        return articles
```

## License

Private - Tidxo Technology Co., Ltd.
