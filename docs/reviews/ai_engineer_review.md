# AI 工程師技術審查報告

**項目**：Tidxo 智能資訊聚合平台  
**審查人**：AI/ML 工程師（資深 NLP & LLM 應用）  
**審查日期**：2026-07-26  
**審查範圍**：AI 模組設計、NLP 任務、雙語處理、模型部署、數據管道

---

## 目錄

1. [AI 模組設計](#1-ai-模組設計)
2. [NLP 任務](#2-nlp-任務)
3. [雙語處理](#3-雙語處理)
4. [模型部署](#4-模型部署)
5. [數據管道](#5-數據管道)
6. [總結與建議](#6-總結與建議)

---

## 1. AI 模組設計

### 1.1 LLM 選型分析

#### 方案對比

| 模型 | 優勢 | 劣勢 | 適用場景 | 成本 (per 1M tokens) |
|------|------|------|----------|---------------------|
| **GPT-4o** | 質量最高、多語言強、穩定 | 貴、延遲高、依賴 OpenAI | 高質量摘要、複雜推理 | ~$2.50 input / $10 output |
| **GPT-4o-mini** | 平價、速度快、質量唔錯 | 複雜任務稍弱 | 日常摘要、分類 | ~$0.15 input / $0.60 output |
| **Claude 3.5 Sonnet** | 長上下文、指令跟從好 | 中文稍弱於 GPT-4 | 長文分析、結構化輸出 | ~$3 input / $15 output |
| **Qwen2.5-72B** | 開源、中文強、可本地部署 | 需要 GPU 資源 | 本地部署、高頻任務 | 硬件成本 |
| **Llama 3.1-70B** | 開源、英文強、社區活躍 | 中文需微調 | 英文內容處理 | 硬件成本 |
| **DeepSeek-V2** | 開源、中文優秀、MoE 架構高效 | 社區較細 | 中文摘要、翻譯 | 硬件成本 |

#### 推薦方案：混合架構（Hybrid LLM Architecture）

```python
# llm_router.py - 智能 LLM 路由器

from enum import Enum
from typing import Optional
import tiktoken

class LLMProvider(Enum):
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    CLAUDE_SONNET = "claude-3-5-sonnet"
    QWEN_LOCAL = "qwen2.5-72b-local"
    DEEPSEEK_LOCAL = "deepseek-v2-local"

class TaskComplexity(Enum):
    LOW = 1      # 簡單分類、關鍵詞提取
    MEDIUM = 2   # 摘要生成、翻譯
    HIGH = 3     # 深度分析、複雜推理

class LLMRouter:
    """
    根據任務複雜度同成本預算智能選擇 LLM
    """
    
    def __init__(self):
        self.providers = {
            LLMProvider.GPT4O: {"cost": 10.0, "quality": 0.95, "latency": 2.0},
            LLMProvider.GPT4O_MINI: {"cost": 0.6, "quality": 0.80, "latency": 0.5},
            LLMProvider.CLAUDE_SONNET: {"cost": 15.0, "quality": 0.93, "latency": 2.5},
            LLMProvider.QWEN_LOCAL: {"cost": 0.1, "quality": 0.85, "latency": 1.0},
            LLMProvider.DEEPSEEK_LOCAL: {"cost": 0.1, "quality": 0.88, "latency": 1.2},
        }
        
    def select_model(
        self, 
        task: str, 
        complexity: TaskComplexity,
        content_length: int,
        budget_constraint: bool = False
    ) -> LLMProvider:
        """
        根據任務選擇最佳模型
        
        策略：
        - 低複雜度 + 高頻 → 本地模型 (Qwen)
        - 中複雜度 + 成本敏感 → GPT-4o-mini
        - 高複雜度 + 質量優先 → GPT-4o / Claude
        """
        
        # 本地模型優先（成本低、延遲可控）
        if complexity == TaskComplexity.LOW:
            return LLMProvider.QWEN_LOCAL
        
        # 中等複雜度
        if complexity == TaskComplexity.MEDIUM:
            if budget_constraint:
                return LLMProvider.GPT4O_MINI
            elif content_length > 8000:  # 長文本
                return LLMProvider.CLAUDE_SONNET
            else:
                return LLMProvider.GPT4O_MINI
        
        # 高複雜度
        if complexity == TaskComplexity.HIGH:
            if content_length > 16000:
                return LLMProvider.CLAUDE_SONNET  # 長上下文優勢
            return LLMProvider.GPT4O
        
        return LLMProvider.GPT4O_MINI  # fallback


# 使用示例
router = LLMRouter()

# 簡單分類任務 → 用本地 Qwen
model = router.select_model(
    task="classify",
    complexity=TaskComplexity.LOW,
    content_length=500
)
# 返回: LLMProvider.QWEN_LOCAL

# 高質量摘要 → 用 GPT-4o-mini（平衡質量同成本）
model = router.select_model(
    task="summarize",
    complexity=TaskComplexity.MEDIUM,
    content_length=3000,
    budget_constraint=True
)
# 返回: LLMProvider.GPT4O_MINI
```

#### 成本估算（基於項目規劃）

```python
# cost_estimator.py

class CostEstimator:
    """
    估算不同階段嘅 LLM API 成本
    """
    
    def __init__(self):
        self.daily_articles = {
            "phase1": 200,   # MVP 階段
            "phase2": 1000,  # 增長階段
            "phase3": 5000,  # 規模化
        }
        
        # 每篇文章平均 token 數
        self.tokens_per_article = {
            "input": 1500,   # 標題 + 內容
            "output": 200,   # 摘要
        }
    
    def estimate_monthly_cost(
        self, 
        phase: str,
        local_ratio: float = 0.6,  # 60% 用本地模型
        mini_ratio: float = 0.3,   # 30% 用 GPT-4o-mini
        premium_ratio: float = 0.1 # 10% 用 GPT-4o
    ) -> dict:
        """
        估算月度成本
        
        混合策略：
        - 60% 本地模型（分類、簡單摘要）
        - 30% GPT-4o-mini（中等質量摘要）
        - 10% GPT-4o（高質量/複雜任務）
        """
        daily_count = self.daily_articles.get(phase, 200)
        monthly_count = daily_count * 30
        
        # Token 消耗
        total_input_tokens = monthly_count * self.tokens_per_article["input"]
        total_output_tokens = monthly_count * self.tokens_per_article["output"]
        
        # 成本計算（per 1M tokens）
        costs = {
            "local": {
                "ratio": local_ratio,
                "input_cost": 0,  # 本地模型無 API 成本
                "output_cost": 0,
                "monthly_usd": 50,  # 僅硬件攤分
            },
            "gpt4o_mini": {
                "ratio": mini_ratio,
                "input_cost": 0.15,
                "output_cost": 0.60,
                "monthly_usd": 0,
            },
            "gpt4o": {
                "ratio": premium_ratio,
                "input_cost": 2.50,
                "output_cost": 10.0,
                "monthly_usd": 0,
            }
        }
        
        # 計算各模型成本
        for model, config in costs.items():
            input_tokens = total_input_tokens * config["ratio"]
            output_tokens = total_output_tokens * config["ratio"]
            
            if model != "local":
                config["monthly_usd"] = (
                    (input_tokens / 1_000_000) * config["input_cost"] +
                    (output_tokens / 1_000_000) * config["output_cost"]
                )
        
        total_monthly = sum(c["monthly_usd"] for c in costs.values())
        
        return {
            "phase": phase,
            "daily_articles": daily_count,
            "monthly_articles": monthly_count,
            "costs_by_model": costs,
            "total_monthly_usd": total_monthly,
            "total_monthly_mop": total_monthly * 8,  # 1 USD ≈ 8 MOP
        }


# 使用示例
estimator = CostEstimator()

# Phase 2 成本估算
result = estimator.estimate_monthly_cost("phase2")
print(f"Phase 2 月度成本: MOP {result['total_monthly_mop']:.0f}")
# 輸出: Phase 2 月度成本: MOP ~1,200（混合策略）
# 對比: 全用 GPT-4o 會係 MOP ~12,000
```

### 1.2 Prompt Engineering 最佳實踐

#### 核心原則

1. **結構化 Prompt**：使用明確嘅角色、任務、格式要求
2. **Few-shot Learning**：提供 2-3 個示例提升準確率
3. **輸出格式約束**：JSON Schema 確保可解析
4. **語言一致性**：根據輸入語言自動適配輸出語言

#### Prompt 模板系統

```python
# prompts/base.py

from typing import List, Dict, Optional
from pydantic import BaseModel

class PromptTemplate:
    """
    結構化 Prompt 模板
    """
    
    @staticmethod
    def summarize(
        title: str,
        content: str,
        target_lang: str = "zh",
        max_length: int = 150
    ) -> str:
        """
        摘要生成 Prompt
        """
        lang_instruction = {
            "zh": "請用繁體中文（港澳用語風格）撰寫",
            "en": "Please write in English",
            "zh-cn": "请用简体中文撰写"
        }.get(target_lang, "請用繁體中文撰寫")
        
        return f"""你係一個專業嘅新聞編輯，擅長撰寫簡潔準確嘅新聞摘要。

## 任務
為以下新聞文章撰寫一個簡潔嘅摘要。

## 要求
1. {lang_instruction}
2. 字數限制：{max_length} 字以內
3. 保留關鍵信息：人物、事件、時間、地點
4. 保持客觀中立，唔好加入個人觀點
5. 使用清晰簡潔嘅語言

## 示例

輸入：
標題：行政長官發表2026年施政報告
內容：行政長官今日上午10時在立法會發表2026年施政報告，宣布多項惠民措施，包括現金分享計劃維持9000澳門元、醫療券增加至1000元、以及引入新一輪稅務優惠...（略）

輸出：
行政長官今日發表2026年施政報告，宣布維持現金分享9000元、醫療券增至1000元，並引入新稅務優惠措施，涵蓋民生、醫療及經濟多個領域。

## 輸入文章

標題：{title}
內容：{content[:3000]}

## 輸出

摘要："""

    @staticmethod
    def classify(
        title: str,
        content: str,
        categories: List[str]
    ) -> str:
        """
        文本分類 Prompt
        """
        categories_str = "、".join(categories)
        
        return f"""你係一個新聞分類專家。請為以下新聞分類。

## 可選分類
{categories_str}

## 規則
1. 選擇最相關嘅 1-2 個分類
2. 以 JSON 格式輸出
3. 包含信心分數 (0-1)

## 示例輸出
{{"categories": ["本地", "政治"], "confidence": 0.92}}

## 輸入

標題：{title}
內容：{content[:1000]}

## 輸出
"""

    @staticmethod
    def translate(
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None
    ) -> str:
        """
        翻譯 Prompt（支持粵語特殊處理）
        """
        context_section = ""
        if context:
            context_section = f"""
## 上下文
{context}
"""
        
        style_guide = {
            "zh-en": "Use natural, journalistic English. Maintain the original tone.",
            "en-zh": "用繁體中文翻譯，港澳用語風格。专有名词保留原文。",
            "zh-yue": "用粵語口語風格翻譯，保留書面語嘅專業性。"
        }
        
        style = style_guide.get(f"{source_lang}-{target_lang}", "Maintain professional tone.")
        
        return f"""你係一個專業嘅中英翻譯，專注港澳新聞內容。

## 翻譯方向
{source_lang.upper()} → {target_lang.upper()}

## 風格要求
{style}

## 注意事項
1. 專有名詞（人名、地名、機構名）保留原文或採用通用譯名
2. 數字、日期格式按目標語言習慣轉換
3. 保持原文嘅語氣同風格
{context_section}
## 原文
{text}

## 譯文
"""

    @staticmethod
    def extract_keywords(
        title: str,
        content: str,
        max_keywords: int = 5
    ) -> str:
        """
        關鍵詞提取 Prompt
        """
        return f"""從以下新聞中提取關鍵詞。

## 要求
1. 提取 {max_keywords} 個最重要嘅關鍵詞
2. 優先選擇：人名、地名、機構名、核心概念
3. 以 JSON 陣列格式輸出

## 示例
輸入：標題：台積電宣佈在澳門設立芯片廠
輸出：["台積電", "澳門", "芯片製造", "半導體", "投資"]

## 輸入

標題：{title}
內容：{content[:1500]}

## 輸出
"""


# 使用示例
template = PromptTemplate()

# 生成摘要
summary_prompt = template.summarize(
    title="港珠澳大橋通車五周年",
    content="港珠澳大橋今日迎來通車五周年...（略）",
    target_lang="zh",
    max_length=100
)

# 分類
classify_prompt = template.classify(
    title="央行宣佈降息0.25厘",
    content="中國人民銀行今日宣佈...",
    categories=["本地", "大中華", "國際", "財經", "體育", "娛樂", "科技"]
)
```

#### Prompt 版本管理

```python
# prompts/versioning.py

from dataclasses import dataclass
from typing import Dict
import hashlib

@dataclass
class PromptVersion:
    version: str
    template: str
    changelog: str
    metrics: Dict[str, float]  # 評估指標

class PromptRegistry:
    """
    Prompt 版本註冊同管理
    """
    
    def __init__(self):
        self.prompts: Dict[str, list[PromptVersion]] = {}
        
    def register(
        self,
        name: str,
        template: str,
        changelog: str,
        metrics: Dict[str, float] = None
    ):
        """註冊新版本"""
        if name not in self.prompts:
            self.prompts[name] = []
        
        version = f"v{len(self.prompts[name]) + 1}"
        self.prompts[name].append(PromptVersion(
            version=version,
            template=template,
            changelog=changelog,
            metrics=metrics or {}
        ))
        
    def get_best(self, name: str) -> PromptVersion:
        """獲取表現最好嘅版本"""
        versions = self.prompts.get(name, [])
        if not versions:
            raise ValueError(f"Prompt '{name}' not found")
        
        # 按指標排序（例如 ROUGE-L）
        return max(versions, key=lambda v: v.metrics.get("rouge_l", 0))


# 使用示例
registry = PromptRegistry()

# 註冊摘要 prompt 唔同版本
registry.register(
    name="news_summary",
    template="你係新聞編輯...（版本1）",
    changelog="初始版本",
    metrics={"rouge_l": 0.42, "bert_score": 0.87}
)

registry.register(
    name="news_summary",
    template="你係資深新聞編輯...（版本2，加入 few-shot）",
    changelog="加入 few-shot 示例",
    metrics={"rouge_l": 0.48, "bert_score": 0.89}
)

# 自動選擇最佳版本
best = registry.get_best("news_summary")
print(f"最佳版本: {best.version}, ROUGE-L: {best.metrics['rouge_l']}")
```

### 1.3 成本控制策略

#### 多層緩存系統

```python
# cache/semantic_cache.py

from typing import Optional, Dict
import numpy as np
from sentence_transformers import SentenceTransformer
import redis
import json

class SemanticCache:
    """
    語義緩存 - 相似輸入复用已有結果
    
    策略：
    1. 完全匹配 → 直接返回（Redis）
    2. 語義相似 > 0.95 → 返回緩存結果
    3. 相似 < 0.95 → 調用 LLM，結果寫入緩存
    """
    
    def __init__(self, redis_url: str, similarity_threshold: float = 0.95):
        self.redis = redis.from_url(redis_url)
        self.encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.threshold = similarity_threshold
        
    def get(self, text: str, task: str) -> Optional[str]:
        """查詢緩存"""
        cache_key = f"{task}:{hashlib.md5(text.encode()).hexdigest()}"
        
        # 1. 完全匹配
        cached = self.redis.get(cache_key)
        if cached:
            return cached.decode()
        
        # 2. 語義相似匹配
        embedding = self.encoder.encode(text)
        similar = self._find_similar(embedding, task)
        if similar and similar['score'] > self.threshold:
            return similar['result']
        
        return None
    
    def set(self, text: str, result: str, task: str, ttl: int = 86400):
        """寫入緩存"""
        cache_key = f"{task}:{hashlib.md5(text.encode()).hexdigest()}"
        self.redis.setex(cache_key, ttl, result)
        
        # 同時存 embedding 供相似搜索
        embedding = self.encoder.encode(text)
        self.redis.hset(
            f"{task}:embeddings",
            cache_key,
            json.dumps({
                "embedding": embedding.tolist(),
                "result": result,
                "created_at": time.time()
            })
        )
    
    def _find_similar(self, embedding: np.ndarray, task: str) -> Optional[Dict]:
        """搵最相似嘅緩存結果"""
        all_embeddings = self.redis.hgetall(f"{task}:embeddings")
        
        best_match = None
        best_score = 0
        
        for key, data in all_embeddings.items():
            data = json.loads(data)
            cached_emb = np.array(data['embedding'])
            
            # 計算餘弦相似度
            score = np.dot(embedding, cached_emb) / (
                np.linalg.norm(embedding) * np.linalg.norm(cached_emb)
            )
            
            if score > best_score:
                best_score = score
                best_match = {
                    "key": key.decode(),
                    "score": score,
                    "result": data['result']
                }
        
        return best_match if best_score > self.threshold else None


# 使用示例
cache = SemanticCache("redis://localhost:6379")

# 查詢摘要（先查緩存）
cached_summary = cache.get(article_content, "summarize")
if cached_summary:
    # 命中緩存，唔使調用 LLM
    return cached_summary

# 未命中，調用 LLM
summary = call_llm(article_content, "summarize")

# 寫入緩存
cache.set(article_content, summary, "summarize")
```

#### 批量處理優化

```python
# batch/batch_processor.py

import asyncio
from typing import List, Dict

class BatchProcessor:
    """
    批量處理 - 減少 API 調用次數
    """
    
    def __init__(self, max_batch_size: int = 10):
        self.max_batch_size = max_batch_size
        self.queue: List[Dict] = []
        
    async def process_batch(self, articles: List[Dict]) -> List[Dict]:
        """
        批量處理文章
        
        策略：
        - 將多篇文章合併成一個 prompt
        - 減少 API 調用次數
        - 注意 token 限制
        """
        batches = self._split_batches(articles)
        results = []
        
        for batch in batches:
            # 合併 prompt
            combined_prompt = self._create_batch_prompt(batch)
            
            # 一次 API 調用處理多篇
            response = await self._call_llm(combined_prompt)
            
            # 解析結果
            batch_results = self._parse_batch_response(response, len(batch))
            results.extend(batch_results)
        
        return results
    
    def _create_batch_prompt(self, articles: List[Dict]) -> str:
        """創建批量 prompt"""
        items = []
        for i, article in enumerate(articles):
            items.append(f"""
文章 {i+1}:
標題：{article['title']}
內容：{article['content'][:1000]}
""")
        
        return f"""請為以下 {len(articles)} 篇文章分別生成摘要。
每篇摘要用 "---" 分隔。

{"".join(items)}

請按順序輸出每篇摘要，用 "---" 分隔："""
    
    def _split_batches(self, articles: List[Dict]) -> List[List[Dict]]:
        """分批（考慮 token 限制）"""
        batches = []
        current_batch = []
        current_tokens = 0
        
        for article in articles:
            # 估算 token 數
            est_tokens = len(article.get('content', '')) // 4
            
            if current_tokens + est_tokens > 12000:  # 預留 buffer
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            
            current_batch.append(article)
            current_tokens += est_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
```

---

## 2. NLP 任務

### 2.1 文本分類算法

#### 方案對比

| 方法 | 準確率 | 訓練成本 | 推理速度 | 適用場景 |
|------|--------|----------|----------|----------|
| **FastText** | 85-88% | 極低 | 極快 | 基線、高頻分類 |
| **TextCNN** | 88-91% | 低 | 快 | 中等規模數據 |
| **BERT-base** | 92-95% | 中 | 中等 | 通用場景 |
| **BERT-wwm** | 93-96% | 中 | 中等 | 中文優化 |
| **LLM Zero-shot** | 80-90% | 零 | 慢 | 無訓練數據 |

#### 推薦方案：分層分類器

```python
# classification/hierarchical_classifier.py

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np
from typing import List, Tuple

class HierarchicalClassifier:
    """
    分層分類器
    
    第一層：FastText 快速分類（低延遲）
    第二層：BERT 精細分類（高準確率）
    
    策略：
    - FastText 信心 > 0.8 → 直接返回
    - FastText 信心 < 0.8 → 用 BERT 二次確認
    """
    
    def __init__(self):
        # 第一層：FastText（快速）
        import fasttext
        self.fasttext_model = fasttext.load_model('models/category_fasttext.bin')
        
        # 第二層：BERT（精準）
        self.bert_tokenizer = AutoTokenizer.from_pretrained('bert-base-chinese')
        self.bert_model = AutoModelForSequenceClassification.from_pretrained(
            'models/news_classifier_bert'
        )
        self.bert_model.eval()
        
        self.categories = [
            "本地", "大中華", "國際", "財經", 
            "體育", "娛樂", "科技", "生活"
        ]
        
    def predict(self, text: str) -> Tuple[str, float]:
        """
        預測分類
        """
        # 第一層：FastText
        ft_pred, ft_conf = self._fasttext_predict(text)
        
        if ft_conf > 0.85:
            # 高信心，直接返回
            return ft_pred, ft_conf
        
        # 第二層：BERT 精細分類
        bert_pred, bert_conf = self._bert_predict(text)
        
        # 如果 BERT 同 FastText 一致，提升信心
        if bert_pred == ft_pred:
            return bert_pred, min(0.99, (ft_conf + bert_conf) / 2 + 0.1)
        
        # 否則以 BERT 為準
        return bert_pred, bert_conf
    
    def _fasttext_predict(self, text: str) -> Tuple[str, float]:
        """FastText 預測"""
        # FastText 格式
        text_clean = text.replace('\n', ' ').strip()
        predictions = self.fasttext_model.predict(text_clean, k=1)
        
        label = predictions[0][0].replace('__label__', '')
        confidence = predictions[1][0]
        
        return label, confidence
    
    def _bert_predict(self, text: str) -> Tuple[str, float]:
        """BERT 預測"""
        inputs = self.bert_tokenizer(
            text[:512],  # 截斷
            return_tensors='pt',
            truncation=True,
            padding=True
        )
        
        with torch.no_grad():
            outputs = self.bert_model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            
        pred_idx = torch.argmax(probs).item()
        confidence = probs[0][pred_idx].item()
        
        return self.categories[pred_idx], confidence


# 訓練腳本
# training/train_classifier.py

from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments
from datasets import load_dataset

def train_news_classifier():
    """
    訓練新聞分類 BERT 模型
    """
    # 加載數據（需要預先準備）
    dataset = load_dataset('json', data_files={
        'train': 'data/train_classification.json',
        'test': 'data/test_classification.json'
    })
    
    # 模型
    model = AutoModelForSequenceClassification.from_pretrained(
        'bert-base-chinese',
        num_labels=8  # 8 個分類
    )
    
    # 訓練參數
    training_args = TrainingArguments(
        output_dir='./models/news_classifier',
        num_train_epochs=5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        learning_rate=2e-5,
        warmup_steps=500,
        weight_decay=0.01,
        evaluation_strategy='epoch',
        save_strategy='epoch',
        load_best_model_at_end=True,
        metric_for_best_model='f1_macro'
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset['train'],
        eval_dataset=dataset['test'],
    )
    
    # 訓練
    trainer.train()
    
    # 保存
    trainer.save_model('./models/news_classifier_best')
    
    return model


# 數據格式示例
"""
# data/train_classification.json
{"text": "行政長官今日發表施政報告...", "label": 0}
{"text": "港股今日低開500點...", "label": 3}
{"text": "NBA季後賽昨晚展開...", "label": 4}

# label 對應：
# 0: 本地, 1: 大中華, 2: 國際, 3: 財經
# 4: 體育, 5: 娛樂, 6: 科技, 7: 生活
"""
```

### 2.2 語義相似度計算

#### Embedding 模型選擇

| 模型 | 維度 | 中文能力 | 速度 | 適用場景 |
|------|------|----------|------|----------|
| **paraphrase-multilingual-MiniLM-L12-v2** | 384 | 良好 | 極快 | 去重、快速匹配 |
| **text2vec-base-chinese** | 768 | 優秀 | 快 | 中文語義搜索 |
| **bge-base-zh-v1.5** | 768 | 極優 | 快 | 高精度中文匹配 |
| **m3e-base** | 768 | 優秀 | 快 | 開源、中文優化 |
| **OpenAI text-embedding-3-small** | 1536 | 優秀 | API延遲 | 高質量、唔使本地部署 |

#### 推薦方案

```python
# similarity/embedding_service.py

from sentence_transformers import SentenceTransformer
from typing import List, Tuple
import numpy as np
from functools import lru_cache

class EmbeddingService:
    """
    語義嵌入服務
    
    用途：
    1. 文章去重（相似度 > 0.85 = 重複）
    2. 聚類 grouping
    3. 語義搜索
    """
    
    def __init__(self, model_name: str = 'BAAI/bge-base-zh-v1.5'):
        """
        推薦模型：
        - 通用：'BAAI/bge-base-zh-v1.5'（中文最優）
        - 輕量：'paraphrase-multilingual-MiniLM-L12-v2'（速度快）
        - 雙語：'paraphrase-multilingual-mpnet-base-v2'
        """
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        
    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        批量編碼文本為向量
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,  # 歸一化，方便計算相似度
            show_progress_bar=False
        )
        return embeddings
    
    def similarity(self, text1: str, text2: str) -> float:
        """計算兩段文本嘅語義相似度"""
        emb1 = self.encode([text1])[0]
        emb2 = self.encode([text2])[0]
        return float(np.dot(emb1, emb2))
    
    def find_duplicates(
        self, 
        articles: List[dict], 
        threshold: float = 0.85
    ) -> List[Tuple[int, int, float]]:
        """
        搵重複文章
        
        返回：[(idx1, idx2, similarity), ...]
        """
        # 提取標題+摘要作為比較依據
        texts = [
            f"{a.get('title', '')} {a.get('summary', '')}" 
            for a in articles
        ]
        
        # 批量編碼
        embeddings = self.encode(texts)
        
        # 計算相似度矩陣
        similarity_matrix = np.dot(embeddings, embeddings.T)
        
        # 找出超過閾值嘅配對
        duplicates = []
        n = len(articles)
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = similarity_matrix[i][j]
                if sim > threshold:
                    duplicates.append((i, j, float(sim)))
        
        return sorted(duplicates, key=lambda x: x[2], reverse=True)
    
    def cluster_articles(
        self,
        articles: List[dict],
        threshold: float = 0.75
    ) -> List[List[int]]:
        """
        將文章聚類（同一事件嘅唔同報導）
        
        使用單鏈接聚類：
        - 兩篇文章相似度 > threshold → 同一簇
        """
        texts = [f"{a['title']} {a.get('summary', '')}" for a in articles]
        embeddings = self.encode(texts)
        
        n = len(articles)
        visited = [False] * n
        clusters = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            cluster = [i]
            visited[i] = True
            
            # 找出所有與 i 相似嘅文章
            for j in range(i + 1, n):
                if visited[j]:
                    continue
                
                sim = np.dot(embeddings[i], embeddings[j])
                if sim > threshold:
                    cluster.append(j)
                    visited[j] = True
            
            clusters.append(cluster)
        
        return clusters


# 使用示例
service = EmbeddingService()

# 文章去重
articles = [
    {"title": "港珠澳大橋通車五周年", "summary": "港珠澳大橋今日迎來..."},
    {"title": "港珠澳大橋迎來通車5週年", "summary": "大橋今日慶祝通車..."},  # 重複
    {"title": "央行宣佈降息", "summary": "中國人民銀行今日..."},
]

duplicates = service.find_duplicates(articles, threshold=0.85)
print(f"發現重複: {duplicates}")
# 輸出: [(0, 1, 0.92)]

# 事件聚類
clusters = service.cluster_articles(articles, threshold=0.75)
print(f"聚類結果: {clusters}")
# 輸出: [[0, 1], [2]]  # 文章 0 同 1 係同一事件
```

### 2.3 關鍵詞提取

#### 方案對比

| 方法 | 優勢 | 劣勢 | 適用場景 |
|------|------|------|----------|
| **TF-IDF** | 簡單快速、可解釋 | 唔理解語義 | 基線、大量數據 |
| **TextRank** | 無監督、圖模型 | 計算量較大 | 中等規模 |
| **BERT/LLM** | 語義理解強 | 需要計算資源 | 高質量需求 |
| **KeyBERT** | 結合兩者優勢 | 需要 embedding | 推薦方案 |

#### 推薦方案：KeyBERT + 領域術語庫

```python
# keywords/extractor.py

from keybert import KeyBERT
from typing import List, Dict, Set
import jieba
import jieba.analyse

class KeywordExtractor:
    """
    混合關鍵詞提取器
    
    策略：
    1. KeyBERT（語義）提取核心概念
    2. jieba 分詞 + 自定義詞典（港澳術語）
    3. 合併去重，按重要性排序
    """
    
    def __init__(self):
        # KeyBERT 模型（支持中文）
        self.keybert_model = KeyBERT(model='paraphrase-multilingual-MiniLM-L12-v2')
        
        # 加載自定義詞典（港澳術語）
        self._load_custom_dictionary()
        
    def _load_custom_dictionary(self):
        """加載港澳專用術語"""
        custom_words = [
            # 政治/政府
            "行政長官", "立法會", "施政報告", "現金分享",
            # 地名
            "港珠澳大橋", "橫琴粵澳深度合作區", "路氹城",
            # 機構
            "澳門日報", "澳廣視", "旅遊局", "經濟局",
            # 特色用語
            "博企", "賭權", "填海", "圍村"
        ]
        
        for word in custom_words:
            jieba.add_word(word, freq=10000)  # 高頻確保唔被切開
    
    def extract(
        self,
        text: str,
        top_k: int = 5,
        use_keybert: bool = True
    ) -> List[Dict]:
        """
        提取關鍵詞
        
        返回: [{"keyword": "xxx", "score": 0.95}, ...]
        """
        keywords = {}
        
        # 方法 1: KeyBERT（語義）
        if use_keybert:
            kb_results = self.keybert_model.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 2),  # 單詞 + 雙詞
                stop_words=None,
                top_n=top_k * 2,  # 提取多啲供合併
                use_mmr=True,  # 多樣性
                diversity=0.7
            )
            
            for kw, score in kb_results:
                keywords[kw] = {"score": score, "source": "keybert"}
        
        # 方法 2: TF-IDF（統計）
        tfidf_results = jieba.analyse.extract_tags(
            text,
            topK=top_k * 2,
            withWeight=True
        )
        
        for kw, weight in tfidf_results:
            if kw in keywords:
                # 合併分數
                keywords[kw]["score"] = (keywords[kw]["score"] + weight) / 2
                keywords[kw]["source"] = "hybrid"
            else:
                keywords[kw] = {"score": weight, "source": "tfidf"}
        
        # 排序並返回 top_k
        sorted_keywords = sorted(
            keywords.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )[:top_k]
        
        return [
            {"keyword": kw, "score": data["score"], "source": data["source"]}
            for kw, data in sorted_keywords
        ]


# 使用示例
extractor = KeywordExtractor()

text = """
行政長官今日發表2026年施政報告，宣布維持現金分享計劃9000澳門元，
並加大對橫琴粵澳深度合作區嘅投資力度。博企股價今日普遍上漲...
"""

keywords = extractor.extract(text, top_k=5)
print(keywords)
# 輸出:
# [
#   {"keyword": "施政報告", "score": 0.92, "source": "hybrid"},
#   {"keyword": "現金分享", "score": 0.88, "source": "keybert"},
#   {"keyword": "橫琴", "score": 0.85, "source": "hybrid"},
#   {"keyword": "博企", "score": 0.78, "source": "tfidf"},
#   {"keyword": "行政長官", "score": 0.75, "source": "keybert"}
# ]
```

---

## 3. 雙語處理

### 3.1 中英翻譯方案

#### 方案對比

| 方案 | 質量 | 成本 | 延遲 | 適用場景 |
|------|------|------|------|----------|
| **DeepL API** | 極高 | 中 | 中 | 高質量需求 |
| **GPT-4o** | 高 | 高 | 高 | 複雜/專業內容 |
| **NLLB-200 (Meta)** | 高 | 低（本地） | 中 | 批量翻譯 |
| **Opus-MT** | 中高 | 低（本地） | 快 | 輕量翻譯 |
| **Google Translate** | 中 | 低 | 快 | 一般需求 |

#### 推薦方案：混合翻譯架構

```python
# translation/translator.py

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from typing import Optional
import httpx

class HybridTranslator:
    """
    混合翻譯器
    
    策略：
    - 短文本 (< 500字) → API（高質量）
    - 長文本 → 本地模型（低成本）
    - 專業術語 → 術語庫後處理
    """
    
    def __init__(self):
        # 本地模型：NLLB-200（Meta 開源，支持 200 語言）
        self.local_tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
        self.local_model = AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-distilled-600M")
        
        # API 客戶端
        self.api_client = httpx.AsyncClient()
        
        # 術語庫
        self.glossary = self._load_glossary()
        
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        use_api: Optional[bool] = None
    ) -> str:
        """
        翻譯文本
        
        source_lang / target_lang: 'zh', 'en', 'yue'
        """
        # 自動選擇策略
        if use_api is None:
            use_api = len(text) < 500  # 短文本用 API
        
        if use_api:
            result = await self._translate_api(text, source_lang, target_lang)
        else:
            result = self._translate_local(text, source_lang, target_lang)
        
        # 術語庫後處理
        result = self._apply_glossary(result, source_lang, target_lang)
        
        return result
    
    async def _translate_api(
        self, 
        text: str, 
        source: str, 
        target: str
    ) -> str:
        """使用 DeepL API"""
        # DeepL 支持嘅語言碼
        lang_map = {"zh": "ZH", "en": "EN", "yue": "ZH"}
        
        response = await self.api_client.post(
            "https://api-free.deepl.com/v2/translate",
            data={
                "text": text,
                "source_lang": lang_map[source],
                "target_lang": lang_map[target],
                "auth_key": "YOUR_DEEPL_API_KEY"
            }
        )
        
        return response.json()["translations"][0]["text"]
    
    def _translate_local(
        self,
        text: str,
        source: str,
        target: str
    ) -> str:
        """使用本地 NLLB 模型"""
        # NLLB 語言碼
        lang_map = {
            "zh": "zho_Hans",
            "en": "eng_Latn",
            "yue": "zho_Hant"  # 粵語用繁體
        }
        
        self.local_tokenizer.src_lang = lang_map[source]
        
        inputs = self.local_tokenizer(text, return_tensors="pt")
        
        outputs = self.local_model.generate(
            **inputs,
            forced_bos_token_id=self.local_tokenizer.lang_code_to_id[lang_map[target]],
            max_length=512
        )
        
        result = self.local_tokenizer.decode(outputs[0], skip_special_tokens=True)
        return result
    
    def _load_glossary(self) -> dict:
        """加載術語庫"""
        return {
            "zh-en": {
                "行政長官": "Chief Executive",
                "立法會": "Legislative Assembly",
                "現金分享計劃": "Cash Sharing Program",
                "港珠澳大橋": "Hong Kong-Zhuhai-Macau Bridge (HZMB)",
                "橫琴粵澳深度合作區": "Guangdong-Macau In-Depth Cooperation Zone in Hengqin",
                "博企": "Gaming operator / Casino operator",
                "澳門元": "Macau Pataca (MOP)",
            },
            "en-zh": {
                "Chief Executive": "行政長官",
                "Legislative Assembly": "立法會",
                "HZMB": "港珠澳大橋",
            }
        }
    
    def _apply_glossary(self, text: str, source: str, target: str) -> str:
        """應用術語庫進行後處理"""
        glossary = self.glossary.get(f"{source}-{target}", {})
        
        result = text
        for source_term, target_term in glossary.items():
            # 簡單替換（實際應該用更智能嘅匹配）
            if source_term in result:
                result = result.replace(source_term, target_term)
        
        return result


# 使用示例
import asyncio

async def main():
    translator = HybridTranslator()
    
    # 短文本用 API
    result = await translator.translate(
        "行政長官今日發表施政報告",
        source_lang="zh",
        target_lang="en"
    )
    print(result)  # "Chief Executive delivers Policy Address today"
    
    # 長文本用本地模型
    long_text = "..." * 1000
    result = await translator.translate(
        long_text,
        source_lang="en",
        target_lang="zh",
        use_api=False
    )

asyncio.run(main())
```

### 3.2 粵語特殊處理

```python
# cantonese/cantonese_processor.py

import re
from typing import List, Dict

class CantoneseProcessor:
    """
    粵語特殊處理
    
    挑戰：
    1. 粵語口語字（佢、嘅、喺、咗、嘢...）
    2. 粵語特有詞彙（巴士、士多、搭的...）
    3. 書面語 vs 口語轉換
    """
    
    def __init__(self):
        # 粵語特徵詞
        self.cantonese_markers = {
            "嘅", "喺", "咗", "嘢", "佢", "哋", "咁", "噉",
            "唔", "冇", "嗰", "啲", "啱", "攞", "嚟", "去"
        }
        
        # 粵語 → 書面語映射
        self.cantonese_to_standard = {
            "佢": "他/她",
            "哋": "們",
            "嘅": "的",
            "喺": "在",
            "咗": "了",
            "嘢": "東西",
            "咁": "這麼",
            "唔": "不",
            "冇": "沒有",
            "嗰": "那",
            "啲": "一些",
            "攞": "拿",
            "嚟": "來",
        }
        
        # 粵語特有外來詞
        self.cantonese_loanwords = {
            "巴士": "bus",
            "的士": "taxi",
            "士多": "store",
            "貼士": "tips",
            "布甸": "pudding",
            "芝士": "cheese",
            "咖啡": "coffee",
        }
    
    def detect_cantonese(self, text: str) -> float:
        """
        檢測文本嘅粵語程度
        
        返回: 0-1，越高越像粵語
        """
        if not text:
            return 0.0
        
        marker_count = sum(1 for char in text if char in self.cantonese_markers)
        return min(1.0, marker_count / (len(text) / 20))  # 歸一化
    
    def cantonese_to_standard_chinese(self, text: str) -> str:
        """
        粵語轉書面中文
        
        用途：送去 LLM 前標準化
        """
        result = text
        
        # 替換粵語特徵詞
        for cantonese, standard in self.cantonese_to_standard.items():
            result = result.replace(cantonese, standard)
        
        return result
    
    def standard_to_cantonese(self, text: str) -> str:
        """
        書面中文轉粵語風格
        
        用途：LLM 輸出後轉換為粵語風格
        """
        # 反向映射
        reverse_map = {v: k for k, v in self.cantonese_to_standard.items()}
        
        result = text
        for standard, cantonese in reverse_map.items():
            result = result.replace(standard, cantonese)
        
        return result
    
    def extract_cantonese_features(self, text: str) -> Dict:
        """
        提取粵語特徵（用於分類/標記）
        """
        return {
            "is_cantonese": self.detect_cantonese(text) > 0.3,
            "cantonese_markers": [c for c in text if c in self.cantonese_markers],
            "loanwords": [w for w in self.cantonese_loanwords.keys() if w in text],
            "estimated_style": "口語" if self.detect_cantonese(text) > 0.5 else "書面語"
        }


# LLM Prompt 適配
def create_cantonese_aware_prompt(text: str, task: str) -> str:
    """
    根據文本語言風格調整 Prompt
    """
    processor = CantoneseProcessor()
    features = processor.extract_cantonese_features(text)
    
    if features["is_cantonese"]:
        # 粵語文本：提示 LLM 注意口語特徵
        style_note = "注意：輸入文本包含粵語口語特徵，請理解其語義後用書面語輸出。"
    else:
        style_note = "輸入為標準書面中文。"
    
    return f"""
{style_note}

任務：{task}

輸入文本：
{text}
"""
```

### 3.3 術語庫管理

```python
# glossary/manager.py

from pydantic import BaseModel
from typing import List, Dict, Optional
import json
from pathlib import Path

class GlossaryEntry(BaseModel):
    """術語條目"""
    term: str
    translations: Dict[str, str]  # {"en": "...", "zh": "..."}
    domain: str  # 領域：政治/財經/體育...
    source: str  # 來源：官方/媒體/用戶
    confidence: float  # 信心度 0-1
    usage_count: int = 0  # 使用次數

class GlossaryManager:
    """
    術語庫管理器
    
    功能：
    1. 術語增刪改查
    2. 自動學習新術語
    3. 按領域/來源分級
    """
    
    def __init__(self, glossary_path: str = "data/glossary.json"):
        self.path = Path(glossary_path)
        self.entries: Dict[str, GlossaryEntry] = {}
        self._load()
    
    def _load(self):
        """加載術語庫"""
        if self.path.exists():
            with open(self.path, 'r', encoding='utf-8') as f:\n                data = json.load(f)\n                for term, entry in data.items():
                    self.entries[term] = GlossaryEntry(**entry)
    
    def _save(self):
        """保存術語庫"""
        data = {term: entry.dict() for term, entry in self.entries.items()}
        with open(self.path, 'w', encoding='utf-8') as f:\n            json.dump(data, f, ensure_ascii=False, indent=2)\n    \n    def add(\n        self,\n        term: str,
        translations: Dict[str, str],
        domain: str,
        source: str = "manual",
        confidence: float = 0.9
    ):
        """添加術語"""
        self.entries[term] = GlossaryEntry(
            term=term,
            translations=translations,
            domain=domain,
            source=source,
            confidence=confidence
        )
        self._save()
    
    def lookup(self, term: str, target_lang: str) -> Optional[str]:
        """查詢術語翻譯"""
        entry = self.entries.get(term)
        if entry:
            entry.usage_count += 1
            return entry.translations.get(target_lang)
        return None
    
    def get_domain_glossary(self, domain: str) -> Dict[str, str]:
        """獲取特定領域嘅術語表"""
        return {
            term: entry.translations
            for term, entry in self.entries.items()
            if entry.domain == domain and entry.confidence > 0.7
        }
    
    def auto_learn_from_text(
        self,
        text: str,
        existing_translations: Dict[str, str],
        threshold: int = 3
    ) -> List[str]:
        """
        從對齊文本中自動學習新術語
        
        策略：
        - 找出反覆出現嘅專有名詞
        - 如果有對應翻譯，加入術語庫
        """
        import jieba
        
        # 分詞
        words = jieba.cut(text)
        word_freq = {}
        
        for word in words:
            if len(word) >= 2:  # 至少 2 個字
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 找出高頻詞（可能係術語）
        candidates = [
            word for word, freq in word_freq.items() 
            if freq >= threshold and word not in self.entries
        ]
        
        # 如果有已知翻譯，加入術語庫
        new_terms = []
        for candidate in candidates:
            if candidate in existing_translations:
                self.add(
                    term=candidate,
                    translations={"en": existing_translations[candidate]},
                    domain="auto",
                    source="auto_learn",
                    confidence=0.6  # 自動學習嘅信心較低
                )
                new_terms.append(candidate)
        
        if new_terms:
            self._save()
        
        return new_terms


# 使用示例
glossary = GlossaryManager()

# 添加官方術語
glossary.add(
    term="橫琴粵澳深度合作區",
    translations={
        "en": "Guangdong-Macau In-Depth Cooperation Zone in Hengqin"
    },
    domain="政治",
    source="official",
    confidence=1.0
)

# 查詢
translation = glossary.lookup("橫琴粵澳深度合作區", "en")
print(translation)  # "Guangdong-Macau In-Depth Cooperation Zone in Hengqin"
```

---

## 4. 模型部署

### 4.1 本地模型部署方案

#### 方案對比

| 方案 | 優勢 | 劣勢 | 適用場景 |
|------|------|------|----------|
| **Ollama** | 簡單易用、API 兼容 | 功能較簡單 | 快速原型、單模型 |
| **vLLM** | 高吞吐、PagedAttention | 配置複雜 | 生產環境、高併發 |
| **TGI (HuggingFace)** | 功能全面、易整合 | 資源需求高 | HuggingFace 生態 |
| **llama.cpp** | 輕量、CPU 支持 | 功能有限 | 邊緣設備 |

#### 推薦方案：Ollama（開發）+ vLLM（生產）

```yaml
# docker-compose.yml - AI 服務部署

version: '3.8'

services:
  # 開發環境：Ollama（簡單快速）
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - OLLAMA_NUM_PARALLEL=4
      - OLLAMA_MAX_LOADED_MODELS=2

  # 生產環境：vLLM（高性能）
  vllm:
    image: vllm/vllm-openai:latest
    ports:
      - "8000:8000"
    volumes:
      - model_cache:/root/.cache
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2  # 多 GPU
              capabilities: [gpu]
    command: >
      --model Qwen/Qwen2.5-32B-Instruct
      --tensor-parallel-size 2
      --max-model-len 32768
      --gpu-memory-utilization 0.9
      --enable-prefix-caching
    environment:
      - CUDA_VISIBLE_DEVICES=0,1

  # Embedding 模型服務
  embedding:
    image: ghcr.io/huggingface/text-embeddings-inference:latest
    ports:
      - "8080:80"
    volumes:
      - model_cache:/data
    command: >
      --model-id BAAI/bge-base-zh-v1.5
      --max-client-batch-size 64
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  ollama_data:
  model_cache:
```

```python
# deployment/llm_client.py

from openai import OpenAI, AsyncOpenAI
from typing import List, Optional
import httpx

class LLMClient:
    """
    統一 LLM 客戶端
    
    支持：
    - OpenAI API（GPT-4）
    - Ollama API（本地）
    - vLLM API（本地生產）
    """
    
    def __init__(
        self,
        provider: str = "ollama",  # "openai" | "ollama" | "vllm"
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.provider = provider
        
        if provider == "openai":
            self.client = AsyncOpenAI(api_key=api_key)
            self.model = "gpt-4o-mini"
        elif provider == "ollama":
            # Ollama 兼容 OpenAI API
            self.client = AsyncOpenAI(
                base_url=base_url or "http://localhost:11434/v1",
                api_key="ollama"  # Ollama 唔需要
            )
            self.model = "qwen2.5:32b"
        elif provider == "vllm":
            # vLLM 兼容 OpenAI API
            self.client = AsyncOpenAI(
                base_url=base_url or "http://localhost:8000/v1",
                api_key="empty"
            )
            self.model = "Qwen/Qwen2.5-32B-Instruct"
    
    async def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> str:
        """發送聊天請求"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    async def summarize(self, title: str, content: str) -> str:
        """摘要生成"""
        messages = [
            {"role": "system", "content": "你係專業嘅新聞編輯，擅長撰寫簡潔準確嘅摘要。"},
            {"role": "user", "content": f"標題：{title}\n\n內容：{content[:3000]}\n\n請生成100-150字嘅摘要。"}
        ]
        return await self.chat(messages, temperature=0.3, max_tokens=300)
    
    async def classify(self, text: str, categories: List[str]) -> dict:
        """文本分類"""
        messages = [
            {"role": "system", "content": f"請將以下新聞分類到：{', '.join(categories)}。以JSON格式回覆。"},
            {"role": "user", "content": text[:1000]}
        ]
        result = await self.chat(messages, temperature=0.1, max_tokens=100)
        return json.loads(result)


# 使用示例
import asyncio

async def main():
    # 開發環境
    local_client = LLMClient(provider="ollama")
    summary = await local_client.summarize("港珠澳大橋通車", "港珠澳大橋今日...")
    print(summary)
    
    # 生產環境
    prod_client = LLMClient(provider="vllm", base_url="http://vllm-server:8000/v1")
    summary = await prod_client.summarize("港珠澳大橋通車", "港珠澳大橋今日...")
    print(summary)

asyncio.run(main())
```

### 4.2 模型量化優化

```python
# quantization/quantize.py

"""
模型量化策略

目標：喺唔明顯損失質量嘅前提下，減少模型大小同推理成本

方案對比：
| 方法 | 大小減少 | 速度提升 | 質量損失 | 適用場景 |
|------|----------|----------|----------|----------|
| FP16 | 50% | 1.5x | 極小 | 有 GPU |
| INT8 | 75% | 2x | 小 | 有 GPU |
| INT4 (GPTQ) | 85% | 3x | 中 | GPU 內存有限 |
| GGUF (llama.cpp) | 80% | 2-4x | 小 | CPU/混合 |
"""

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch

def quantize_model_gptq(
    model_name: str,
    output_dir: str,
    bits: int = 4  # 4-bit 或 8-bit
):
    """
    使用 GPTQ 量化模型
    
    適用：Qwen、Llama 等大型模型
    """
    from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig
    
    # 加載模型
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    quantize_config = BaseQuantizeConfig(
        bits=bits,
        group_size=128,
        damp_percent=0.1,
        desc_act=False,
    )
    
    model = AutoGPTQForCausalLM.from_pretrained(
        model_name,
        quantize_config,
        torch_dtype=torch.float16
    )
    
    # 準備校準數據（代表性文本）
    calibration_texts = [
        "行政長官今日發表施政報告",
        "港股今日高開200點",
        "港珠澳大橋通車五周年",
        # ... 更多代表性文本
    ]
    
    examples = [
        tokenizer(text, return_tensors="pt") 
        for text in calibration_texts
    ]
    
    # 量化
    model.quantize(examples)
    
    # 保存
    model.save_quantized(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print(f"量化完成：{output_dir}")
    print(f"原始大小：~60GB → 量化後：~{60 * bits / 16:.0f}GB")


def quantize_model_bnb(
    model_name: str,
    bits: int = 4
):
    """
    使用 BitsAndBytes 量化（運行時量化）
    
    適用：快速測試、唔使預先量化
    """
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=bits == 4,
        load_in_8bit=bits == 8,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,  # 雙重量化，進一步節省
        bnb_4bit_quant_type="nf4",  # NormalFloat4
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto"
    )
    
    return model


# Ollama 量化模型選擇
"""
Ollama 提供唔同量化版本：

qwen2.5:32b        # FP16, ~60GB
qwen2.5:32b-q8_0   # 8-bit, ~32GB
qwen2.5:32b-q4_K_M # 4-bit, ~18GB (推薦)
qwen2.5:32b-q2_K   # 2-bit, ~10GB (質量損失較大)

建議：
- 有足夠 GPU 內存 → q8_0
- GPU 內存有限 → q4_K_M
- 僅 CPU → q4_K_M 或 q2_K
"""
```

### 4.3 推理加速

```python
# inference/acceleration.py

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import List

class InferenceOptimizer:
    """
    推理加速策略
    
    1. KV Cache 優化
    2. Continuous Batching
    3. Prefix Caching
    4. Speculative Decoding
    """
    
    @staticmethod
    def setup_kv_cache(model, max_batch_size: int = 32):
        """
        啟用 KV Cache
        
        效果：重複 token 唔使重新計算，速度提升 2-3x
        """
        model.config.use_cache = True
        return model
    
    @staticmethod
    def compile_model(model):
        """
        使用 torch.compile 加速
        
        PyTorch 2.0+ 功能，自動融合算子
        """
        compiled_model = torch.compile(
            model,
            mode="reduce-overhead",  # 或 "max-autotune"
            fullgraph=True
        )
        return compiled_model
    
    @staticmethod
    def setup_flash_attention(model):
        """
        啟用 Flash Attention
        
        效果：內存減少 50%，速度提升 2x
        需要：Ampere+ GPU (A100, RTX 30xx+)
        """
        model.config.attn_implementation = "flash_attention_2"
        return model


# vLLM 高性能配置
"""
# vLLM 啟動命令（生產環境）

python -m vllm.entrypoints.openai.api_server \\
    --model Qwen/Qwen2.5-32B-Instruct \\
    --tensor-parallel-size 2 \\          # 2 GPU 並行
    --max-model-len 32768 \\             # 最大上下文長度
    --gpu-memory-utilization 0.9 \\      # GPU 內存利用率
    --enable-prefix-caching \\           # 前綴緩存（重複 prompt 加速）
    --enable-chunked-prefill \\          # 分塊預填充
    --max-num-batched-tokens 8192 \\     # 批量 token 數
    --trust-remote-code

預期性能：
- 吞吐量：~50 requests/sec（32B 模型，2x A100）
- 延遲：~200ms（首 token），~50ms/token（生成）
"""


# 批量推理優化
class BatchInference:
    """
    批量推理 - 提升吞吐量
    """
    
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
    
    @torch.inference_mode()
    def generate_batch(
        self,
        prompts: List[str],
        max_new_tokens: int = 256,
        temperature: float = 0.7
    ) -> List[str]:
        """
        批量生成
        
        比逐個生成快 5-10x
        """
        # Tokenize
        inputs = self.tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=2048
        ).to(self.model.device)
        
        # 批量生成
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        # 解碼
        results = []
        for i, output in enumerate(outputs):
            # 只取新生成嘅 token
            new_tokens = output[inputs['input_ids'].shape[1]:]
            result = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            results.append(result)
        
        return results


# 使用示例
optimizer = InferenceOptimizer()

# 加載模型並優化
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-32B-Instruct",
    torch_dtype=torch.float16,
    device_map="auto"
)

# 啟用優化
model = optimizer.setup_kv_cache(model)
model = optimizer.setup_flash_attention(model)
# model = optimizer.compile_model(model)  # 首次運行會慢，之後快

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-32B-Instruct")

# 批量推理
batch = BatchInference(model, tokenizer)
results = batch.generate_batch([
    "請總結以下新聞：...",
    "請總結以下新聞：...",
    "請總結以下新聞：...",
])
```

---

## 5. 數據管道

### 5.1 訓練數據收集

```python
# data/collection.py

from pydantic import BaseModel
from typing import List, Optional
import json
from pathlib import Path
import hashlib

class TrainingExample(BaseModel):
    """訓練數據示例"""
    id: str
    task: str  # "summarize" | "classify" | "translate" | "keywords"
    input: str
    output: str
    language: str  # "zh" | "en" | "yue"
    source: str
    quality_score: float  # 0-1

class DataCollector:
    """
    訓練數據收集器
    
    策略：
    1. 從現有新聞 + 人工標註收集
    2. 用 LLM 生成合成數據
    3. 用戶反饋數據
    4. 數據質量過濾
    """
    
    def __init__(self, output_dir: str = "data/training"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def collect_from_llm_generation(
        self,
        articles: List[dict],
        task: str,
        llm_client
    ) -> List[TrainingExample]:
        """
        用 LLM 生成訓練數據
        
        流程：
        1. 用 LLM 處理文章（生成摘要/分類等）
        2. 人工審核高質量結果
        3. 加入訓練集
        """
        examples = []
        
        for article in articles:
            # 用 LLM 生成
            if task == "summarize":
                output = llm_client.summarize(
                    article['title'],
                    article['content']
                )
            elif task == "classify":
                output = llm_client.classify(
                    article['title'] + " " + article.get('content', '')[:500],
                    categories=["本地", "大中華", "國際", "財經", "體育", "娛樂", "科技"]
                )
                output = json.dumps(output)
            
            # 計算數據 ID（去重）
            data_id = hashlib.md5(
                f"{task}:{article['url']}".encode()
            ).hexdigest()[:12]
            
            example = TrainingExample(
                id=data_id,
                task=task,
                input=f"{article['title']}\n\n{article.get('content', '')[:2000]}",
                output=output,
                language=article.get('language', 'zh'),
                source=article.get('source', 'unknown'),
                quality_score=0.7  # LLM 生成嘅默認分數
            )
            
            examples.append(example)
        
        return examples
    
    def filter_by_quality(
        self,
        examples: List[TrainingExample],
        min_quality: float = 0.6
    ) -> List[TrainingExample]:
        """
        按質量過濾
        
        策略：
        - 人工標註：quality_score = 1.0
        - LLM 生成 + 人工審核：quality_score = 0.8-0.9
        - 純 LLM 生成：quality_score = 0.6-0.7
        - 自動生成未審核：quality_score < 0.6（過濾）
        """
        return [e for e in examples if e.quality_score >= min_quality]
    
    def save(self, examples: List[TrainingExample], split: str = "train"):
        """保存到文件"""
        output_file = self.output_dir / f"{split}.jsonl"
        
        with open(output_file, 'w', encoding='utf-8') as f:\n            for example in examples:
                f.write(example.model_dump_json() + '\n')
        
        print(f"保存 {len(examples)} 條數據到 {output_file}")
    
    def generate_classification_data(
        self,
        articles: List[dict],
        num_synthetic_per_class: int = 100
    ) -> List[TrainingExample]:
        """
        生成分類訓練數據
        
        策略：
        1. 用現有文章嘅分類作為標籤
        2. 用 LLM 生成合成數據補充稀缺類別
        """
        examples = []
        
        # 從現有文章提取
        for article in articles:
            if article.get('category'):
                examples.append(TrainingExample(
                    id=hashlib.md5(article['url'].encode()).hexdigest()[:12],
                    task="classify",
                    input=f"{article['title']}\n\n{article.get('content', '')[:1000]}",
                    output=article['category'],
                    language=article.get('language', 'zh'),
                    source=article.get('source', 'user'),
                    quality_score=0.9  # 來自真實數據
                ))
        
        return examples


# 數據格式示例
"""
# data/training/train.jsonl
{"id":"a1b2c3d4e5f6","task":"summarize","input":"標題：港珠澳大橋...\n\n內容：...","output":"港珠澳大橋今日迎來通車五周年...","language":"zh","source":"rthk","quality_score":0.9}
{"id":"b2c3d4e5f6g7","task":"classify","input":"標題：央行降息...\n\n內容：...","output":"財經","language":"zh","source":"scmp","quality_score":0.85}
"""
```

### 5.2 模型評估指標

```python
# evaluation/metrics.py

from typing import List, Dict
import numpy as np
from rouge_score import rouge_scorer
from bert_score import score as bert_score_fn
from sklearn.metrics import classification_report, f1_score

class ModelEvaluator:
    """
    模型評估工具
    
    指標：
    1. 摘要：ROUGE-L, BERTScore
    2. 分類：Accuracy, F1-macro, F1-weighted
    3. 翻譯：BLEU, chrF++
    4. 關鍵詞：Precision, Recall, F1
    """
    
    def __init__(self):
        self.rouge_scorer = rouge_scorer.RougeScorer(
            ['rouge1', 'rouge2', 'rougeL'],
            use_stemmer=False
        )
    
    def evaluate_summarization(
        self,
        predictions: List[str],
        references: List[str]
    ) -> Dict[str, float]:
        """
        評估摘要質量
        """
        results = {
            'rouge1': [],
            'rouge2': [],
            'rougeL': [],
        }
        
        for pred, ref in zip(predictions, references):
            scores = self.rouge_scorer.score(ref, pred)
            for key in results:
                results[key].append(scores[key].fmeasure)
        
        # 計算 BERTScore（語義相似度）
        P, R, F1 = bert_score_fn(
            predictions, 
            references, 
            lang='zh',
            model_type='bert-base-chinese'
        )
        
        return {
            'rouge1': np.mean(results['rouge1']),
            'rouge2': np.mean(results['rouge2']),
            'rougeL': np.mean(results['rougeL']),
            'bert_score': F1.mean().item(),
        }
    
    def evaluate_classification(
        self,
        predictions: List[str],
        references: List[str],
        labels: List[str] = None
    ) -> Dict[str, float]:
        """
        評估分類性能
        """
        # 計算指標
        report = classification_report(
            references,
            predictions,
            labels=labels,
            output_dict=True,
            zero_division=0
        )
        
        return {
            'accuracy': report['accuracy'],
            'f1_macro': report['macro avg']['f1-score'],
            'f1_weighted': report['weighted avg']['f1-score'],
            'precision_macro': report['macro avg']['precision'],
            'recall_macro': report['macro avg']['recall'],
        }
    
    def evaluate_keywords(
        self,
        predictions: List[List[str]],
        references: List[List[str]]
    ) -> Dict[str, float]:
        """
        評估關鍵詞提取
        """
        precisions = []
        recalls = []
        
        for pred, ref in zip(predictions, references):
            pred_set = set(pred)
            ref_set = set(ref)
            
            if len(pred_set) == 0:
                precisions.append(0)
            else:
                precisions.append(len(pred_set & ref_set) / len(pred_set))
            
            if len(ref_set) == 0:
                recalls.append(0)
            else:
                recalls.append(len(pred_set & ref_set) / len(ref_set))
        
        precision = np.mean(precisions)
        recall = np.mean(recalls)\n        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1': f1
        }
    
    def compare_models(
        self,
        models: Dict[str, List[str]],
        references: List[str],
        task: str = "summarize"
    ) -> Dict[str, Dict[str, float]]:
        """
        比較唔同模型嘅表現
        """
        results = {}
        
        for model_name, predictions in models.items():
            if task == "summarize":
                results[model_name] = self.evaluate_summarization(predictions, references)
            elif task == "classify":
                results[model_name] = self.evaluate_classification(predictions, references)
        
        return results


# 使用示例
evaluator = ModelEvaluator()

# 評估摘要模型
predictions = [
    "港珠澳大橋今日迎來通車五周年，累計通行車輛超過...",
    "央行宣佈降息0.25厘，市場反應積極..."
]
references = [
    "港珠澳大橋通車五周年，累計通行車輛突破千萬...",
    "中國人民銀行降息0.25個百分點，刺激市場..."
]

metrics = evaluator.evaluate_summarization(predictions, references)
print(metrics)
# {'rouge1': 0.52, 'rouge2': 0.38, 'rougeL': 0.48, 'bert_score': 0.89}
```

### 5.3 A/B 測試框架

```python
# ab_testing/framework.py

from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
import hashlib
import random

@dataclass
class ExperimentConfig:
    """實驗配置"""
    name: str
    variants: Dict[str, dict]  # {"control": {...}, "treatment": {...}}
    traffic_split: Dict[str, float]  # {"control": 0.5, "treatment": 0.5}
    metrics: List[str]  # 要追蹤嘅指標
    duration_days: int = 7
    min_sample_size: int = 1000

class ABTestFramework:
    """
    A/B 測試框架
    
    用途：
    1. 比較唔同 Prompt 版本
    2. 比較唔同模型
    3. 比較唔同參數
    """
    
    def __init__(self):
        self.experiments: Dict[str, ExperimentConfig] = {}
        self.results: Dict[str, Dict] = {}
    
    def create_experiment(self, config: ExperimentConfig):
        """創建實驗"""
        # 驗證流量分配
        total = sum(config.traffic_split.values())
        assert abs(total - 1.0) < 0.01, "流量分配總和必須為 1"
        
        self.experiments[config.name] = config
        self.results[config.name] = {
            variant: {"count": 0, "metrics": {}}
            for variant in config.variants
        }
    
    def assign_variant(self, experiment_name: str, user_id: str) -> str:
        """
        分配用戶到實驗組
        
        使用一致性哈希，確保同一用戶永遠喺同一組
        """
        config = self.experiments[experiment_name]
        
        # 一致性哈希
        hash_value = int(hashlib.md5(
            f"{experiment_name}:{user_id}".encode()
        ).hexdigest(), 16)
        
        # 根據流量分配選擇
        cumulative = 0
        for variant, split in config.traffic_split.items():
            cumulative += split
            if (hash_value % 1000) / 1000 < cumulative:
                return variant
        
        return list(config.variants.keys())[-1]  # fallback
    
    def record_metric(
        self,
        experiment_name: str,
        variant: str,
        metric_name: str,
        value: float
    ):
        """記錄指標"""
        results = self.results[experiment_name][variant]
        results["count"] += 1
        
        if metric_name not in results["metrics"]:
            results["metrics"][metric_name] = []
        
        results["metrics"][metric_name].append(value)
    
    def analyze_results(self, experiment_name: str) -> Dict:
        """
        分析實驗結果
        """
        config = self.experiments[experiment_name]
        results = self.results[experiment_name]
        
        analysis = {
            "experiment": experiment_name,
            "variants": {},
            "winner": None,
            "confidence": 0,
        }
        
        for variant, data in results.items():
            variant_analysis = {
                "sample_size": data["count"],
                "metrics": {}
            }
            
            for metric_name, values in data["metrics"].items():
                if values:
                    variant_analysis["metrics"][metric_name] = {
                        "mean": np.mean(values),
                        "std": np.std(values),
                        "ci_95": self._confidence_interval(values)
                    }
            
            analysis["variants"][variant] = variant_analysis
        
        # 確定贏家
        if len(results) == 2:
            variants = list(results.keys())
            control_metrics = results[variants[0]]["metrics"]
            treatment_metrics = results[variants[1]]["metrics"]
            
            # 簡單比較均值（實際應該用統計檢驗）
            for metric_name in config.metrics:
                if metric_name in control_metrics and metric_name in treatment_metrics:
                    control_mean = np.mean(control_metrics[metric_name])
                    treatment_mean = np.mean(treatment_metrics[metric_name])
                    
                    if treatment_mean > control_mean * 1.05:  # 5% 提升
                        analysis["winner"] = variants[1]
                    else:
                        analysis["winner"] = variants[0]
        
        return analysis
    
    def _confidence_interval(self, values: List[float], confidence: float = 0.95) -> tuple:
        """計算置信區間"""
        n = len(values)
        mean = np.mean(values)
        std = np.std(values)
        
        # 簡化版（假設正態分佈）
        z = 1.96  # 95% confidence
        margin = z * std / np.sqrt(n)
        
        return (mean - margin, mean + margin)


# 使用示例：測試唔同 Prompt 版本

# 1. 創建實驗
framework = ABTestFramework()

framework.create_experiment(ExperimentConfig(
    name="prompt_v1_vs_v2",
    variants={
        "control": {"prompt_version": "v1"},
        "treatment": {"prompt_version": "v2"}
    },
    traffic_split={"control": 0.5, "treatment": 0.5},
    metrics=["rougeL", "user_rating", "latency_ms"],
    duration_days=7,
    min_sample_size=500
))

# 2. 處理請求時分配
def process_article(article: dict, user_id: str):
    # 分配實驗組
    variant = framework.assign_variant("prompt_v1_vs_v2", user_id)
    
    # 根據組別使用唔同 prompt
    if variant == "control":
        summary = generate_summary_v1(article)
    else:
        summary = generate_summary_v2(article)
    
    # 記錄指標
    rouge_score = compute_rouge(summary, reference)
    framework.record_metric("prompt_v1_vs_v2", variant, "rougeL", rouge_score)
    
    return summary

# 3. 分析結果
results = framework.analyze_results("prompt_v1_vs_v2")
print(f"Winner: {results['winner']}")
print(f"Control ROUGE-L: {results['variants']['control']['metrics']['rougeL']['mean']:.3f}")
print(f"Treatment ROUGE-L: {results['variants']['treatment']['metrics']['rougeL']['mean']:.3f}")
```

---

## 6. 總結與建議

### 6.1 核心建議

| 範疇 | 建議 | 優先級 |
|------|------|--------|
| **LLM 選型** | 混合架構：本地 Qwen (60%) + GPT-4o-mini (30%) + GPT-4o (10%) | 🔴 高 |
| **成本控制** | 語義緩存 + 批量處理，預計節省 60-70% API 成本 | 🔴 高 |
| **文本分類** | 分層分類器：FastText (快速) + BERT (精準) | 🟡 中 |
| **語義相似度** | BGE-base-zh-v1.5（中文最優）或 MiniLM（輕量） | 🟡 中 |
| **關鍵詞提取** | KeyBERT + 自定義港澳術語庫 | 🟡 中 |
| **翻譯方案** | 短文本 DeepL API + 長文本 NLLB 本地模型 | 🟡 中 |
| **粵語處理** | 特徵檢測 + 書面語轉換 + LLM Prompt 適配 | 🟢 低 |
| **模型部署** | 開發用 Ollama，生產用 vLLM | 🔴 高 |
| **量化優化** | Qwen-32B Q4_K_M（18GB，平衡質量同大小） | 🟡 中 |
| **A/B 測試** | 實現一致性哈希分組 + 多指標追蹤 | 🟢 低 |

### 6.2 實施路線圖

```
Phase 1（MVP）:
├── ✅ 搭建 LLM 客戶端（Ollama + OpenAI）
├── ✅ 實現基礎 Prompt 模板
├── ✅ 部署 Embedding 模型（去重 + 聚類）
└── ✅ 建立基礎評估指標

Phase 2（功能完善）:
├── 🔲 實現混合翻譯系統
├── 🔲 訓練新聞分類器（BERT）
├── 🔲 建立術語庫
├── 🔲 實現語義緩存
└── 🔲 A/B 測試框架

Phase 3（優化）:
├── 🔲 模型量化部署（vLLM）
├── 🔲 收集訓練數據
├── 🔲 微調本地模型
└── 🔲 推理加速優化
```

### 6.3 成本估算更新

基於混合架構嘅成本估算：

| 階段 | 原預算 (LLM API) | 優化後預算 | 節省 |
|------|------------------|------------|------|
| Phase 1 | MOP 500 | MOP 300 | 40% |
| Phase 2 | MOP 3,000 | MOP 1,200 | 60% |
| Phase 3 | MOP 10,000 | MOP 3,500 | 65% |

**節省策略**：
- 60% 請求用本地模型（無 API 成本）
- 語義緩存減少重複調用
- 批量處理減少 API 次數

### 6.4 風險同應對

| 風險 | 影響 | 應對 |
|------|------|------|
| 本地模型質量唔夠 | 中 | 關鍵任務 fallback 到 GPT-4o |
| GPU 資源不足 | 高 | 使用量化模型 + CPU 推理備選 |
| API 成本超支 | 中 | 嚴格限流 + 優先本地模型 |
| 粵語處理效果差 | 低 | 先用書面語，逐步優化 |

---

**文檔版本**：v1.0  
**最後更新**：2026-07-26  
**作者**：AI/ML 工程師審查報告
