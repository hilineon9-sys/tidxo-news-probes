# Tidxo 數據工程師技術審查報告

**審查人角色**：資深數據工程師  
**審查日期**：2026-07-26  
**審查範圍**：數據管道、存儲方案、數據治理、分析平台、合規隱私

---

## 1. 數據管道設計

### 1.1 ETL 流程設計 — 審查意見

項目計劃提出嘅三階段管道（Raw → Clean → Cluster）方向正確，但有以下建議：

#### 問題 1：缺少 Staging 層

計劃中清洗同聚類係一步過完成，建議拆做三層（Medallion Architecture）：

```
Bronze（原始）→ Silver（清洗）→ Gold（聚合/分析）
```

**原因**：
- 原始數據要保留，方便日後重跑 pipeline 或排查問題
- 清洗邏輯變更時唔使重新爬取
- 方便做數據質量監控（Bronze vs Silver 對比）

#### 問題 2：Celery 唔適合做複雜編排

計劃用 Celery + Redis 做異步任務，但當 pipeline 變複雜（多步依賴、失敗重試、條件分支）時，Celery 嘅 DAG 能力好弱。

**建議**：Phase 1 用 Celery 快速起步係可以，但 Phase 2 應該遷移到專門嘅 workflow engine：

| 方案 | 適用場景 | 備註 |
|------|---------|------|
| **Prefect** | 輕量、Pythonic | 推薦，學習曲線低 |
| **Dagster** | 數據感知型編排 | 適合有複雜數據依賴嘅場景 |
| **Temporal** | 高可靠微服務編排 | 適合 Phase 3 微服務拆分後 |

#### 問題 3：缺少 Dead Letter Queue

探針採集失敗嘅數據直接丟棄？建議加 DLQ：

```python
# 建議嘅 pipeline 結構
class ProbePipeline:
    async def run(self, source: str):
        try:
            raw = await self.fetch(source)
            validated = self.validate(raw)  # Pydantic validation
            await self.store_bronze(validated)  # 存原始數據
            
            cleaned = self.clean(validated)
            await self.store_silver(cleaned)
            
            clustered = self.cluster(cleaned)
            await self.store_gold(clustered)
        except ProbeError as e:
            await self.send_to_dlq(source, e)  # 死信隊列
            logger.error(f"Probe {source} failed: {e}")
```

### 1.2 實時處理 vs 批處理

計劃中冇明確區分，建議按場景劃分：

| 場景 | 處理方式 | 延遲要求 | 技術選型 |
|------|---------|---------|---------|
| 新聞採集 | 微批（Micro-batch） | 5-15 分鐘 | Celery Beat / Prefect |
| Breaking News 推送 | 實時（Stream） | < 30 秒 | Redis Streams / Kafka |
| 去重檢測 | 近實時 | 1-5 分鐘 | Redis + Bloom Filter |
| AI 摘要生成 | 異步批處理 | 10-30 分鐘 | Celery Worker Pool |
| 用戶行為分析 | 批處理 | 每小時/每日 | Cron + Batch Job |
| 推薦系統更新 | 微批 | 每 15 分鐘 | Prefect Schedule |

**代碼示例 — Redis Streams 做 Breaking News 實時管道**：

```python
import redis
from redis.commands.json.path import Path

class RealtimeNewsStream:
    """Breaking News 實時處理管道"""
    
    def __init__(self, redis_url: str):
        self.r = redis.from_url(redis_url)
        self.stream_key = "news:incoming"
        self.consumer_group = "news_processors"
    
    async def publish(self, article: dict):
        """探針發佈新文章到 stream"""
        if article.get("priority") == "breaking":
            await self.r.xadd(
                self.stream_key,
                {"article": json.dumps(article), "priority": "breaking"},
                maxlen=10000  # 限制 stream 長度
            )
    
    async def consume(self):
        """消費端：實時處理 breaking news"""
        try:
            self.r.xgroup_create(
                self.stream_key, self.consumer_group, id="0", mkstream=True
            )
        except redis.ResponseError:
            pass  # Group already exists
        
        while True:
            messages = self.r.xreadgroup(
                groupname=self.consumer_group,
                consumername="processor-1",
                streams={self.stream_key: ">"},
                count=10,
                block=5000  # 5秒超時
            )
            for stream, entries in messages:
                for msg_id, data in entries:
                    await self._process_breaking(json.loads(data["article"]))
                    self.r.xack(self.stream_key, self.consumer_group, msg_id)
```

### 1.3 數據質量保證

計劃中完全冇提及數據質量框架，呢個係大風險。建議：

#### 建議方案：Great Expectations

```python
# expectations/article_quality.py
from great_expectations.core import ExpectationSuite, ExpectationConfiguration

def build_article_suite() -> ExpectationSuite:
    suite = ExpectationSuite("article_quality")
    
    # 基本完整性
    suite.add_expectation(ExpectationConfiguration(
        expectation_type="expect_column_values_to_not_be_null",
        kwargs={"column": "title"}
    ))
    suite.add_expectation(ExpectationConfiguration(
        expectation_type="expect_column_values_to_not_be_null",
        kwargs={"column": "url"}
    ))
    
    # 數據合理性
    suite.add_expectation(ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={"column": "title_length", "min_value": 5, "max_value": 500}
    ))
    
    # 時效性
    suite.add_expectation(ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_date_parseable",
        kwargs={"column": "published_at"}
    ))
    
    # 去重
    suite.add_expectation(ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_unique",
        kwargs={"column": "url"}
    ))
    
    return suite
```

#### 數據質量監控指標

| 維度 | 指標 | 閾值 | 告警方式 |
|------|------|------|---------|
| 完整性 | 空標題率 | < 1% | Slack 告警 |
| 準確性 | URL 可達率 | > 98% | 每小時檢查 |
| 時效性 | 採集延遲 | < 15 分鐘 | Prometheus alert |
| 一致性 | 重複率 | < 5% | 每日報告 |
| 唯一性 | URL 唯一性 | 100% | Pipeline 阻斷 |

---

## 2. 存儲方案

### 2.1 數據庫選型分析

計劃選咗 PostgreSQL 做主數據庫，呢個選擇合理但唔完整。隨住數據量增長，需要分層存儲：

#### 推薦存儲架構

```
┌─────────────────────────────────────────────────────────┐
│                    存儲分層架構                           │
├──────────────┬──────────────────────────────────────────┤
│ 熱數據       │ PostgreSQL 15 (OLTP)                     │
│ (< 30天)     │ - 用戶數據、最近文章、書籤                  │
│              │ - 全文搜索用 pg_trgm + zhparser           │
├──────────────┼──────────────────────────────────────────┤
│ 搜索層       │ Elasticsearch 8                          │
│ (全量)       │ - 全文搜索、聚合分析、Faceted Search       │
│              │ - 中文分詞用 IK Analyzer                  │
├──────────────┼──────────────────────────────────────────┤
│ 溫數據       │ PostgreSQL (Partition by month)           │
│ (30-365天)   │ - 歷史文章、閱讀記錄                      │
│              │ - 按月分區，自動 drop 老分區               │
├──────────────┼──────────────────────────────────────────┤
│ 冷數據       │ S3/MinIO + Parquet                       │
│ (> 1年)      │ - 歸檔數據、審計日誌                      │
│              │ - 列式存儲，方便分析查詢                   │
├──────────────┼──────────────────────────────────────────┤
│ 時序數據     │ TimescaleDB (PostgreSQL Extension)        │
│              │ - 用戶行為事件、系統 metrics               │
│              │ - 自動壓縮、連續聚合                      │
└──────────────┴──────────────────────────────────────────┘
```

#### 點解唔建議 MongoDB？

| 考量 | PostgreSQL | MongoDB |
|------|-----------|---------|
| 事務支持 | ✅ ACID | ⚠️ 多文檔事務性能差 |
| 全文搜索 | ✅ pg_trgm + zhparser | ⚠️ 基礎文本搜索 |
| JSON 支持 | ✅ jsonb + GIN index | ✅ 原生 |
| 數據一致性 | ✅ 強一致 | ⚠️ 最終一致 |
| 運維成本 | ✅ 單一數據庫 | ❌ 額外集群 |
| 港澳人才池 | ✅ 較多 | ⚠️ 較少 |

**結論**：Phase 1-2 用 PostgreSQL 足夠。MongoDB 喺呢個場景冇明顯優勢，反而增加運維複雜度。

#### 幾時要引入 ClickHouse？

當你需要做以下分析時先考慮：
- 百萬級以上文章嘅聚合分析
- 用戶行為嘅實時 OLAP 查詢
- 複雜嘅時間序列聚合

```sql
-- ClickHouse 示例：用戶閱讀行為分析
SELECT
    toDate(read_at) AS date,
    category,
    count() AS reads,
    avg(read_duration) AS avg_duration,
    uniqExact(user_id) AS unique_readers
FROM reading_events
WHERE read_at >= now() - INTERVAL 30 DAY
GROUP BY date, category
ORDER BY date DESC, reads DESC
```

**建議時間線**：Phase 1-2 用 PostgreSQL + ES，Phase 3 用戶量過萬後引入 ClickHouse 做 OLAP。

### 2.2 Elasticsearch 優化

計劃中提到用 ES 8 做全文搜索，以下係具體優化建議：

#### Mapping 設計

```json
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "ik_max_word",
        "search_analyzer": "ik_smart",
        "fields": {
          "keyword": { "type": "keyword" },
          "pinyin": { "type": "text", "analyzer": "pinyin_analyzer" }
        }
      },
      "content": {
        "type": "text",
        "analyzer": "ik_max_word",
        "search_analyzer": "ik_smart"
      },
      "summary": {
        "type": "text",
        "analyzer": "ik_smart"
      },
      "tags": { "type": "keyword" },
      "category": { "type": "keyword" },
      "source": { "type": "keyword" },
      "language": { "type": "keyword" },
      "published_at": { "type": "date" },
      "embedding": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      }
    }
  },
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "pinyin_analyzer": {
          "tokenizer": "pinyin_tokenizer",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "pinyin_tokenizer": {
          "type": "pinyin",
          "keep_first_letter": true,
          "keep_full_pinyin": false
        }
      }
    }
  }
}
```

#### 性能優化要點

```python
# 1. 批量索引（唔好逐條 insert）
from elasticsearch.helpers import bulk

def index_articles(es_client, articles):
    actions = [
        {
            "_index": "articles",
            "_id": article["url"],  # 用 URL 做 ID，天然去重
            "_source": article
        }
        for article in articles
    ]
    success, errors = bulk(es_client, actions, chunk_size=500, refresh="wait_until")
    return success

# 2. 搜索優化：用 filter context 代替 query（唔計算 relevance score）
def search_articles(query: str, filters: dict):
    return es.search(
        index="articles",
        body={
            "query": {
                "bool": {
                    "must": [
                        {"multi_match": {
                            "query": query,
                            "fields": ["title^3", "summary^2", "content"],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }}
                    ],
                    "filter": [
                        {"term": filters.get("category")} if filters.get("category") else None,
                        {"range": {"published_at": {"gte": "now-7d"}}} if filters.get("recent") else None,
                    ]
                }
            },
            "highlight": {
                "fields": {"title": {}, "summary": {}},
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"]
            },
            "size": 20
        }
    )

# 3. 語義搜索（用 embedding 做相似度）
def semantic_search(embedding: list[float], top_k: int = 10):
    return es.search(
        index="articles",
        knn={
            "field": "embedding",
            "query_vector": embedding,
            "k": top_k,
            "num_candidates": 100
        }
    )
```

### 2.3 時序數據存儲

計劃中 `reading_history` 表會隨時間快速膨脹。建議用 **TimescaleDB**（PostgreSQL 擴展）：

```sql
-- 安裝 TimescaleDB 擴展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 將閱讀歷史轉為 hypertable
CREATE TABLE reading_events (
    time TIMESTAMPTZ NOT NULL,
    user_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    read_duration INTEGER,
    scroll_depth FLOAT,  -- 新增：閱讀深度百分比
    device_type VARCHAR(20),
    session_id UUID
);

SELECT create_hypertable('reading_events', 'time');

-- 自動壓縮（7天前的數據）
SELECT add_compression_policy('reading_events', INTERVAL '7 days');

-- 連續聚合：每小時統計
CREATE MATERIALIZED VIEW reading_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    article_id,
    count(*) AS read_count,
    avg(read_duration) AS avg_duration,
    avg(scroll_depth) AS avg_scroll
FROM reading_events
GROUP BY bucket, article_id;

-- 自動刷新
SELECT add_continuous_aggregate_policy('reading_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);
```

**好處**：
- 查詢性能提升 10-100x（對比普通 PostgreSQL）
- 自動壓縮，存儲節省 90%+
- 連續聚合，實時分析唔使全表掃描
- 完全兼容 PostgreSQL 生態

---

## 3. 數據治理

### 3.1 數據目錄管理

計劃中完全冇提及數據目錄，呢個喺 Phase 2 之後會成為痛點。建議用 **DataHub** 或 **OpenMetadata**：

#### 推薦方案：OpenMetadata（輕量級）

```yaml
# docker-compose.yml 片段
openmetadata:
  image: openmetadata/server:1.2
  environment:
    DB_DRIVER_CLASS: org.postgresql.Driver
    DB_URL: jdbc:postgresql://postgres:5432/openmetadata
  ports:
    - "8585:8585"
```

#### 數據目錄應該記錄嘅元數據

```yaml
# metadata/article_table.yml
table:
  name: articles
  database: tidxo_main
  description: "核心文章表，存儲所有採集到嘅新聞文章"
  columns:
    - name: id
      type: SERIAL
      description: "主鍵"
      constraints: PRIMARY KEY
    - name: source
      type: VARCHAR(100)
      description: "新聞來源標識（如 rthk, scmp）"
      tags: ["pii:source", "lineage:probe"]
    - name: title
      type: VARCHAR(500)
      description: "文章標題"
      tags: ["searchable", "translated"]
    - name: url
      type: VARCHAR(1000)
      description: "原文 URL，唯一約束"
      tags: ["pii:url", "dedup-key"]
    - name: tags
      type: TEXT[]
      description: "AI 生成嘅標籤列表"
      tags: ["ai-generated", "searchable"]
  owner: data-team@tidxo.com
  tier: Tier-1  # 核心業務表
```

### 3.2 數據血緣追蹤

建議用 **OpenLineage** 標準，記錄數據從源頭到最終消費嘅完整路徑：

```python
from openlineage.client import OpenLineageClient
from openlineage.client.run import RunEvent, EventType, Run, Job, Dataset

class LineageTracker:
    """追蹤數據管道中嘅血緣關係"""
    
    def __init__(self):
        self.client = OpenLineageClient.from_environment()
    
    def track_probe_run(self, source: str, articles_count: int):
        """記錄探針採集事件"""
        event = RunEvent(
            eventType=EventType.COMPLETE,
            eventTime=datetime.now().isoformat(),
            run=Run(runId=str(uuid4())),
            job=Job(namespace="tidxo/probes", name=f"probe_{source}"),
            inputs=[],  # 外部新聞源
            outputs=[
                Dataset(
                    namespace="tidxo/postgres",
                    name="tidxo_main.articles",
                    facets={}
                )
            ]
        )
        self.client.emit(event)
    
    def track_aggregation(self, input_table: str, output_table: str):
        """記錄聚合處理"""
        event = RunEvent(
            eventType=EventType.COMPLETE,
            eventTime=datetime.now().isoformat(),
            run=Run(runId=str(uuid4())),
            job=Job(namespace="tidxo/pipeline", name="aggregation"),
            inputs=[Dataset(namespace="tidxo/postgres", name=input_table)],
            outputs=[Dataset(namespace="tidxo/postgres", name=output_table)]
        )
        self.client.emit(event)
```

**血緣可視化效果**：
```
[RTHK Probe] ──→ [articles (Bronze)] ──→ [articles_clean (Silver)] ──→ [ES Index]
[SCMP Probe] ──→        ↑                        ↓
[TVB Probe] ──→         ↑              [article_clusters (Gold)]
                         ↑                        ↓
                  [DLQ: failed_articles]   [推薦系統] [分析報表]
```

### 3.3 數據版本控制

#### Schema 遷移管理

```python
# 用 Alembic 做 PostgreSQL schema 版本控制
# alembic/versions/001_create_articles.py

def upgrade():
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('url', sa.String(1000), nullable=False, unique=True),
        sa.Column('summary', sa.Text),
        sa.Column('content', sa.Text),
        sa.Column('author', sa.String(200)),
        sa.Column('category', sa.String(100)),
        sa.Column('language', sa.String(10), server_default='zh'),
        sa.Column('image_url', sa.String(1000)),
        sa.Column('published_at', sa.DateTime),
        sa.Column('fetched_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('tags', sa.ARRAY(sa.Text)),
        sa.Column('view_count', sa.Integer, server_default='0'),
        sa.Column('embedding', sa.Text),  # JSON 存儲向量
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_articles_published', 'articles', ['published_at'])
    op.create_index('idx_articles_tags', 'articles', ['tags'], postgresql_using='gin')

def downgrade():
    op.drop_table('articles')
```

#### 數據快照（Snapshot）

```python
# 用 S3/MinIO 做定期快照
class DataSnapshotManager:
    def create_snapshot(self, table: str, partition: str = None):
        """每日快照，方便回溯"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query = f"SELECT * FROM {table}"
        if partition:
            query += f" WHERE created_at::date = '{partition}'"
        
        # 導出為 Parquet 格式（列式存儲，壓縮率高）
        df = pd.read_sql(query, engine)
        path = f"s3://tidxo-snapshots/{table}/{timestamp}.parquet"
        df.to_parquet(path, compression="zstd", engine="pyarrow")
        
        # 記錄快照元數據
        self.register_snapshot(table, path, len(df))
    
    def restore_snapshot(self, table: str, snapshot_path: str):
        """從快照恢復數據"""
        df = pd.read_parquet(snapshot_path)
        df.to_sql(table, engine, if_exists="append", index=False)
```

---

## 4. 分析平台

### 4.1 用戶行為分析

計劃中提到用 Mixpanel/Amplitude，但考慮到成本同數據主權，建議自建 + 開源方案：

#### 推薦方案：PostHog（開源替代品）

```python
# 事件追蹤 SDK
from posthog import Posthog

posthog = Posthog('your-api-key', host='https://posthog.tidxo.com')

# 追蹤閱讀事件
def track_reading(user_id: int, article: dict, duration: int, scroll_depth: float):
    posthog.capture(
        distinct_id=str(user_id),
        event='article_read',
        properties={
            'article_id': article['id'],
            'category': article['category'],
            'source': article['source'],
            'language': article['language'],
            'tags': article['tags'],
            'read_duration_seconds': duration,
            'scroll_depth_pct': scroll_depth,
            'time_of_day': datetime.now().hour,
            'device': request.headers.get('user-agent'),
        }
    )

# 追蹤推送點擊
def track_push_click(user_id: int, article: dict, push_type: str):
    posthog.capture(
        distinct_id=str(user_id),
        event='push_clicked',
        properties={
            'article_id': article['id'],
            'push_type': push_type,  # breaking / daily_digest / personalized
            'time_to_read': (datetime.now() - push_sent_at).seconds,
        }
    )
```

#### 自定義分析 Pipeline

```python
class UserBehaviorAnalyzer:
    """用戶行為分析引擎"""
    
    def __init__(self, db_engine, es_client):
        self.db = db_engine
        self.es = es_client
    
    def get_engagement_metrics(self, user_id: int) -> dict:
        """計算用戶參與度指標"""
        with self.db.connect() as conn:
            # 7日活躍度
            recent_reads = conn.execute(text("""
                SELECT count(*), avg(read_duration), 
                       count(DISTINCT article_id) as unique_articles,
                       count(DISTINCT category) as categories_explored
                FROM reading_events
                WHERE user_id = :uid 
                AND time >= now() - INTERVAL '7 days'
            """), {"uid": user_id}).fetchone()
            
            return {
                "reads_7d": recent_reads[0],
                "avg_duration_7d": float(recent_reads[1] or 0),
                "unique_articles_7d": recent_reads[2],
                "categories_explored": recent_reads[3],
                "engagement_score": self._calc_engagement_score(recent_reads),
            }
    
    def _calc_engagement_score(self, metrics) -> float:
        """
        參與度評分（0-100）：
        - 閱讀頻率：40%
        - 閱讀時長：30%
        - 內容多樣性：20%
        - 互動行為：10%（書籤、分享）
        """
        reads = min(metrics[0] or 0, 50)  # cap at 50
        duration = min(metrics[1] or 0, 600)  # cap at 10 min
        unique = min(metrics[2] or 0, 30)
        categories = min(metrics[3] or 0, 8)
        
        score = (
            (reads / 50) * 40 +
            (duration / 600) * 30 +
            (unique / 30) * 20 +
            (categories / 8) * 10
        )
        return round(score, 1)
    
    def get_content_performance(self, days: int = 7) -> list:
        """內容表現分析"""
        # 用 ES 做聚合分析
        result = self.es.search(
            index="articles",
            body={
                "size": 0,
                "query": {"range": {"published_at": {"gte": f"now-{days}d"}}},
                "aggs": {
                    "by_category": {
                        "terms": {"field": "category", "size": 10},
                        "aggs": {
                            "avg_views": {"avg": {"field": "view_count"}},
                            "total_reads": {"sum": {"field": "view_count"}},
                            "avg_read_duration": {
                                "avg": {"field": "avg_read_duration"}
                            }
                        }
                    },
                    "by_source": {
                        "terms": {"field": "source", "size": 20},
                        "aggs": {
                            "article_count": {"value_count": {"field": "_id"}},
                            "avg_views": {"avg": {"field": "view_count"}}
                        }
                    },
                    "hourly_trend": {
                        "date_histogram": {
                            "field": "published_at",
                            "calendar_interval": "hour"
                        }
                    }
                }
            }
        )
        return result["aggregations"]
```

### 4.2 內容分析指標

#### 核心指標體系

```python
class ContentMetrics:
    """內容分析指標定義"""
    
    # === 文章層面 ===
    ARTICLE_METRICS = {
        "virality_score": "分享數 / 閱讀數 × 100",
        "engagement_depth": "平均閱讀時長 / 預估閱讀時長",
        "completion_rate": "閱讀到底嘅用戶比例（scroll > 90%）",
        "bounce_rate": "閱讀 < 10秒就離開嘅比例",
        "comment_density": "評論數 / 閱讀數 × 1000",
    }
    
    # === 分類層面 ===
    CATEGORY_METRICS = {
        "content_velocity": "每日新增文章數",
        "reader_acquisition": "新用戶首次閱讀該分類嘅比例",
        "reader_retention": "連續 3 日閱讀該分類嘅用戶比例",
        "cross_category_rate": "同時閱讀其他分類嘅比例",
    }
    
    # === 來源層面 ===
    SOURCE_METRICS = {
        "freshness_score": "從發佈到收錄嘅平均時間（分鐘）",
        "unique_content_ratio": "獨家/首發內容比例",
        "quality_score": "平均閱讀時長 × 完成率",
        "reliability": "探針成功率（技術層面）",
    }
```

### 4.3 商業智能報表

#### 推薦方案：Apache Superset（開源 BI）

```yaml
# docker-compose.yml
superset:
  image: apache/superset:3.1
  environment:
    SUPERSET_SECRET_KEY: "your-secret-key"
    DATABASE_URL: postgresql://user:pass@postgres:5432/superset
  ports:
    - "8088:8088"
  volumes:
    - superset_data:/app/superset_home
```

#### 關鍵報表 Dashboard

| Dashboard | 受眾 | 更新頻率 | 核心指標 |
|-----------|------|---------|---------|
| 運營總覽 | CEO/產品 | 實時 | DAU、留存、營收 |
| 內容健康度 | 編輯團隊 | 每小時 | 文章數、分類分佈、熱門話題 |
| 探針監控 | 工程團隊 | 每 5 分鐘 | 成功率、延遲、錯誤率 |
| 用戶增長 | 市場團隊 | 每日 | 註冊、激活、流失漏斗 |
| 推薦效果 | 算法團隊 | 每 15 分鐘 | CTR、覆蓋率、多樣性 |

#### SQL 示例 — 用戶留存漏斗

```sql
-- 7日留存率計算
WITH first_action AS (
    SELECT user_id, MIN(time::date) AS first_date
    FROM reading_events
    GROUP BY user_id
),
daily_active AS (
    SELECT DISTINCT user_id, time::date AS active_date
    FROM reading_events
)
SELECT
    f.first_date,
    COUNT(DISTINCT f.user_id) AS new_users,
    COUNT(DISTINCT CASE 
        WHEN d.active_date = f.first_date + 1 THEN f.user_id 
    END) AS day1_retained,
    COUNT(DISTINCT CASE 
        WHEN d.active_date = f.first_date + 3 THEN f.user_id 
    END) AS day3_retained,
    COUNT(DISTINCT CASE 
        WHEN d.active_date = f.first_date + 7 THEN f.user_id 
    END) AS day7_retained,
    COUNT(DISTINCT CASE 
        WHEN d.active_date = f.first_date + 30 THEN f.user_id 
    END) AS day30_retained
FROM first_action f
LEFT JOIN daily_active d ON f.user_id = d.user_id
GROUP BY f.first_date
ORDER BY f.first_date DESC;
```

---

## 5. 合規與隱私

### 5.1 個人資料保護（PDPO）

香港《個人資料（私隱）條例》要求，以下係具體實現：

#### 數據分類標記

```python
from enum import Enum

class DataClassification(Enum):
    PUBLIC = "public"           # 公開數據（新聞內容）
    INTERNAL = "internal"       # 內部使用
    CONFIDENTIAL = "confidential"  # 機密（用戶行為）
    RESTRICTED = "restricted"   # 受限（個人身份資料）

class PIIType(Enum):
    EMAIL = "email"
    NAME = "name"
    IP_ADDRESS = "ip_address"
    DEVICE_ID = "device_id"
    READING_HISTORY = "reading_history"
    LOCATION = "location"  # 如果有定位功能
```

#### 加密存儲

```python
from cryptography.fernet import Fernet
import hashlib

class PIIEncryption:
    """敏感數據加密存儲"""
    
    def __init__(self, key: bytes):
        self.fernet = Fernet(key)
    
    def encrypt_email(self, email: str) -> str:
        """加密存儲用戶 email"""
        return self.fernet.encrypt(email.encode()).decode()
    
    def decrypt_email(self, encrypted: str) -> str:
        return self.fernet.decrypt(encrypted.encode()).decode()
    
    def hash_for_lookup(self, email: str) -> str:
        """用 hash 做查詢（唔使解密）"""
        return hashlib.sha256(email.encode()).hexdigest()

# 數據庫層面
# ALTER TABLE users ADD COLUMN email_encrypted TEXT;
# ALTER TABLE users ADD COLUMN email_hash VARCHAR(64) UNIQUE;
# 遷移完成後 DROP COLUMN email;
```

#### 知情同意管理

```python
class ConsentManager:
    """用戶同意管理（PDPO 第3原則）"""
    
    def record_consent(self, user_id: int, purposes: list[str], version: str):
        """記錄用戶同意（必須可審計）"""
        consent = {
            "user_id": user_id,
            "purposes": purposes,  # ["personalization", "analytics", "marketing"]
            "consent_version": version,
            "granted_at": datetime.now(),
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent"),
        }
        db.execute(text("""
            INSERT INTO consent_records 
            (user_id, purposes, consent_version, granted_at, ip_address, user_agent)
            VALUES (:user_id, :purposes, :version, :granted_at, :ip, :ua)
        """), consent)
    
    def check_consent(self, user_id: int, purpose: str) -> bool:
        """檢查用戶是否同意特定用途"""
        result = db.execute(text("""
            SELECT purposes FROM consent_records
            WHERE user_id = :uid AND revoked_at IS NULL
            ORDER BY granted_at DESC LIMIT 1
        """), {"uid": user_id}).fetchone()
        
        if not result:
            return False
        return purpose in result[0]
    
    def withdraw_consent(self, user_id: int, purpose: str):
        """撤回同意（PDPO 要求可隨時撤回）"""
        db.execute(text("""
            UPDATE consent_records 
            SET revoked_at = NOW()
            WHERE user_id = :uid AND revoked_at IS NULL
        """), {"uid": user_id})
        
        # 觸發數據處理：停止該用途嘅數據使用
        self._stop_data_usage(user_id, purpose)
```

### 5.2 數據保留政策

```python
class DataRetentionPolicy:
    """
    數據保留策略（PDPO 第2原則：數據應在目的達成後刪除）
    
    建議保留期限：
    - 新聞文章：永久（公共信息）
    - 用戶帳戶：帳號存續期間 + 30天
    - 閱讀歷史：90天（之後聚合統計）
    - 推送記錄：30天
    - 搜索記錄：30天
    - 日誌數據：90天
    - 備份快照：30天滾動
    """
    
    RETENTION_DAYS = {
        "reading_events": 90,
        "push_events": 30,
        "search_events": 30,
        "session_logs": 90,
        "consent_records": None,  # 永久保留（合規要求）
        "articles": None,  # 永久（公共信息）
        "user_accounts": None,  # 帳號存續期間
    }
    
    def run_cleanup(self):
        """每日執行數據清理"""
        for table, days in self.RETENTION_DAYS.items():
            if days is None:
                continue
            
            # 先聚合到長期存儲
            self._archive_before_delete(table, days)
            
            # 然後刪除
            db.execute(text(f"""
                DELETE FROM {table}
                WHERE created_at < NOW() - INTERVAL '{days} days'
            """))
            logger.info(f"Cleaned {table}: removed data older than {days} days")
    
    def _archive_before_delete(self, table: str, days: int):
        """刪除前先歸檔到 S3"""
        cutoff = f"NOW() - INTERVAL '{days} days'"
        query = f"SELECT * FROM {table} WHERE created_at < {cutoff}"
        df = pd.read_sql(query, engine)
        
        if len(df) > 0:
            path = f"s3://tidxo-archive/{table}/{datetime.now():%Y%m%d}.parquet"
            df.to_parquet(path, compression="zstd")
            logger.info(f"Archived {len(df)} rows from {table} to {path}")
```

### 5.3 用戶數據刪除機制（被遺忘權）

```python
class DataErasureService:
    """
    用戶數據刪除服務（PDPO 第6原則：查閱權 + 更正權）
    
    刪除流程：
    1. 用戶提交刪除請求
    2. 驗證身份
    3. 標記帳戶為「待刪除」（30天冷靜期）
    4. 軟刪除所有個人數據
    5. 30天後硬刪除 + 清理備份
    """
    
    def request_deletion(self, user_id: int, reason: str = None):
        """步驟 1-3：提交刪除請求"""
        db.execute(text("""
            UPDATE users 
            SET deletion_requested_at = NOW(),
                deletion_reason = :reason,
                account_status = 'pending_deletion'
            WHERE id = :uid
        """), {"uid": user_id, "reason": reason})
        
        # 發送確認郵件
        self._send_deletion_confirmation(user_id)
        
        # 排程 30 天後執行硬刪除
        celery_app.send_task(
            "tasks.hard_delete_user",
            args=[user_id],
            countdown=30 * 24 * 3600  # 30天後
        )
    
    def soft_delete(self, user_id: int):
        """步驟 4：軟刪除（可恢復）"""
        tables_to_clean = [
            ("bookmarks", "user_id"),
            ("reading_events", "user_id"),
            ("push_events", "user_id"),
            ("search_events", "user_id"),
            ("user_preferences", "user_id"),
        ]
        
        for table, col in tables_to_clean:
            db.execute(text(f"DELETE FROM {table} WHERE {col} = :uid"), {"uid": user_id})
        
        # 匿名化用戶資料（保留統計需要）
        db.execute(text("""
            UPDATE users SET
                email = 'deleted_' || id || '@deleted.tidxo.com',
                name = 'Deleted User',
                avatar_url = NULL,
                interests = '{}',
                account_status = 'deleted',
                deleted_at = NOW()
            WHERE id = :uid
        """), {"uid": user_id})
        
        # 清理 ES 中嘅用戶相關數據
        es.delete_by_query(
            index="user_events",
            body={"query": {"term": {"user_id": user_id}}}
        )
    
    def hard_delete(self, user_id: int):
        """步驟 5：硬刪除（不可恢復）"""
        db.execute(text("DELETE FROM users WHERE id = :uid AND account_status = 'deleted'"), 
                   {"uid": user_id})
        
        # 清理備份中的引用（標記）
        db.execute(text("""
            INSERT INTO deletion_audit_log (user_id, deleted_at, backup_cleanup_status)
            VALUES (:uid, NOW(), 'pending')
        """), {"uid": user_id})
    
    def export_user_data(self, user_id: int) -> str:
        """
        數據可攜帶權（用戶要求匯出自己嘅數據）
        返回 JSON 格式嘅用戶數據包
        """
        user = db.execute(text("SELECT * FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
        bookmarks = db.execute(text("SELECT * FROM bookmarks WHERE user_id = :uid"), {"uid": user_id}).fetchall()
        history = db.execute(text("SELECT * FROM reading_events WHERE user_id = :uid"), {"uid": user_id}).fetchall()
        
        export = {
            "profile": dict(user),
            "bookmarks": [dict(b) for b in bookmarks],
            "reading_history": [dict(h) for h in history],
            "exported_at": datetime.now().isoformat(),
        }
        
        # 存到 S3，生成下載連結（24小時有效）
        path = f"s3://tidxo-exports/{user_id}/{datetime.now():%Y%m%d%H%M%S}.json"
        s3.put_object(Bucket="tidxo-exports", Key=path, Body=json.dumps(export))
        return self._generate_presigned_url(path, expires_in=86400)
```

---

## 6. 總結與優先級建議

### 即刻要做（Phase 1）

| 優先級 | 項目 | 工作量 | 理由 |
|--------|------|--------|------|
| 🔴 P0 | Alembic schema 遷移管理 | 1天 | 冇版本控制會出大問題 |
| 🔴 P0 | 數據加密存儲（email） | 2天 | PDPO 合規底線 |
| 🟡 P1 | Dead Letter Queue | 1天 | 數據唔能丟 |
| 🟡 P1 | TimescaleDB 安裝 | 1天 | reading_history 會快速膨脹 |
| 🟡 P1 | 數據保留策略實現 | 2天 | 合規要求 |

### 短期要做（Phase 2）

| 優先級 | 項目 | 工作量 | 理由 |
|--------|------|--------|------|
| 🟡 P1 | Great Expectations 數據質量 | 1週 | pipeline 可靠性 |
| 🟡 P1 | OpenLineage 血緣追蹤 | 3天 | 問題排查 |
| 🟢 P2 | PostHog 用戶行為分析 | 1週 | 產品決策依據 |
| 🟢 P2 | Superset BI Dashboard | 3天 | 可視化 |

### 中長期（Phase 3）

| 優先級 | 項目 | 工作量 | 理由 |
|--------|------|--------|------|
| 🟢 P2 | ClickHouse OLAP | 2週 | 大規模分析 |
| 🟢 P2 | Prefect 替代 Celery | 1週 | 複雜編排 |
| 🔵 P3 | OpenMetadata 數據目錄 | 1週 | 團隊協作 |
| 🔵 P3 | Kafka 替代 Redis Streams | 2週 | 高吞吐 |

### ⚠️ 關鍵風險提醒

1. **數據庫分區**：`articles` 表一定要按月分區，否則半年後查詢會明顯變慢
2. **ES 索引生命週期**：設定 ILM Policy，舊索引自動 shrink + freeze
3. **備份策略**：PostgreSQL 用 pg_basebackup + WAL archive，確保 RPO < 1小時
4. **GDPR/PDPO**：如果將來有歐洲用戶，合規要求更嚴格，建議一開始就按最高標準設計

---

**文檔版本**：v1.0  
**審查人**：Data Engineer Agent  
**日期**：2026-07-26
