# Tidxo 智能資訊聚合平台 — 架構師審查報告

**審查人**：資深系統架構師（分佈式系統方向）  
**審查日期**：2026-07-26  
**文檔版本**：PROJECT_PLAN v1.0  

---

## 目錄

1. [架構優化](#1-架構優化)
2. [可擴展性設計](#2-可擴展性設計)
3. [高可用方案](#3-高可用方案)
4. [性能優化](#4-性能優化)
5. [安全架構](#5-安全架構)
6. [總結與優先級建議](#6-總結與優先級建議)

---

## 1. 架構優化

### 1.1 微服務拆分策略

#### 現狀評估

PROJECT_PLAN 已經規劃咗 6 個微服務（Probe / Aggregation / AI / User / Notification / Analytics），方向正確。但有以下問題：

- **Aggregation Service 職責過重**：清洗、去重、分類、聚類全部塞喺一個服務，會成為性能瓶頸
- **AI Service 耦合風險**：LLM 調用同本地模型推理混喺一齊，資源消耗模式完全唔同
- **缺少獨立嘅內容服務**：文章 CRUD 同搜索散落在多處

#### 建議拆分方案

```
┌──────────────────────────────────────────────────────────────────┐
│                     API Gateway (Kong / Envoy)                    │
└──────────────────────────────────────────────────────────────────┘
         │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼
┌────────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│  Content   ││  Probe   ││Pipeline  ││   AI     ││   User   │
│  Service   ││ Service  ││ Service  ││ Service  ││ Service  │
│            ││          ││          ││          ││          │
│ - 文章CRUD ││ - 採集   ││ - 清洗   ││ - 摘要   ││ - 認證   │
│ - 搜索     ││ - 解析   ││ - 去重   ││ - 翻譯   ││ - 偏好   │
│ - 分類管理 ││ - 調度   ││ - 分類   ││ - 標籤   ││ - 書籤   │
│ - 版本管理 ││ - 代理池 ││ - 聚類   ││ - 情感   ││ - 歷史   │
└────────────┘└──────────┘└──────────┘└──────────┘└──────────┘
         │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼
┌────────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│Notification││Analytics ││  Admin   ││Recommend ││Billing   │
│  Service   ││ Service  ││ Service  ││ Service  ││ Service  │
│            ││          ││          ││          ││(Phase 4) │
│ - 推送     ││ - 行為   ││ - 源管理 ││ - 協同   ││ - 訂閱   │
│ - Email    ││ - 指標   ││ - 探針   ││ - 內容   ││ - 支付   │
│ - WebSocket││ - 報表   ││ - 審計   ││ - 排序   ││ - 帳單   │
└────────────┘└──────────┘└──────────┘└──────────┘└──────────┘
```

**關鍵拆分原則**：

| 服務 | 拆分理由 | 獨立部署優勢 |
|------|---------|-------------|
| **Content Service** | 文章係核心實體，讀寫量最大 | 可獨立擴容 read replica |
| **Probe Service** | I/O 密集，需要獨立調度 | 可按源分配資源，隔離故障 |
| **Pipeline Service** | CPU 密集（去重/分類） | 可用 GPU 實例，獨立擴展 |
| **AI Service** | LLM 調用延遲高、成本高 | 可限流、降級、用異步 |
| **Recommend Service** | Phase 2 先需要，邏輯複雜 | 可獨立迭代，唔影響核心 |

#### 拆分時機建議

```
Phase 1（MVP）：Monolith-ish
  → Content + User + Probe 合做一個服務
  → Pipeline 用 Celery worker 獨立進程
  → AI 用同步調用，後期再拆

Phase 2：拆分 Content / Probe / AI
  → 引入 Kafka 做事件總線
  → Pipeline 獨立部署

Phase 3：完整微服務
  → 所有服務獨立部署
  → 引入 Service Mesh（Istio）
```

### 1.2 服務間通訊機制

#### 同步 vs 異步矩陣

| 場景 | 通訊方式 | 協議 | 理由 |
|------|---------|------|------|
| API → Content Service | **同步** | gRPC / REST | 用戶等待響應，需要低延遲 |
| Probe → Pipeline | **異步** | Kafka / Redis Stream | 採集完即扔，唔等處理 |
| Pipeline → AI Service | **異步** | Kafka | LLM 調用慢，阻塞會拖死 Pipeline |
| Pipeline → Content Service | **異步** | Kafka | 處理完寫入，唔需要即時確認 |
| Notification → 用戶 | **異步** | FCM / WebSocket | 推送本身就係異步 |
| Content → Search Index | **異步** | Kafka → ES | 搜索索引最終一致即可 |
| User → Recommend | **異步** | Redis Stream | 行為數據異步收集 |

#### 事件驅動架構（Event-Driven）

```
┌──────────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐
│  Probe   │────▶│           │────▶│ Pipeline │────▶│ Content  │
│  Service │     │   Kafka   │     │ Service  │     │ Service  │
└──────────┘     │           │     └──────────┘     └──────────┘
                 │  Topics:  │          │                │
┌──────────┐     │ - raw     │          ▼                ▼
│   User   │────▶│ - cleaned │     ┌──────────┐     ┌──────────┐
│  Action  │     │ - ai-done │     │   AI     │     │   ES     │
└──────────┘     │ - indexed │     │ Service  │────▶│  Index   │
                 │ - notify  │     └──────────┘     └──────────┘
                 └───────────┘          │
                      │                 ▼
                      │           ┌──────────┐
                      └──────────▶│Notification│
                                  │  Service  │
                                  └──────────┘
```

**Kafka Topic 設計**：

```
tidxo.raw-articles          # Probe 產出嘅原始文章
tidxo.cleaned-articles      # Pipeline 清洗後
tidxo.ai-processed          # AI 處理完成（摘要/翻譯/標籤）
tidxo.published-articles    # 正式發布到 Content Service
tidxo.user-events           # 用戶行為（閱讀/收藏/分享）
tidxo.notifications         # 推送任務
```

**點解揀 Kafka 而唔係 RabbitMQ**：
- 文章處理係 stream processing 場景，Kafka 天然適合
- 消息需要持久化同重放（Pipeline 掛咗可以重跑）
- 吞吐量遠高於 RabbitMQ
- Phase 1 可以用 Redis Stream 做輕量替代，Phase 2 先上 Kafka

### 1.3 數據一致性保證

#### 分佈式事務策略

**核心原則：最終一致性 + 補償機制**（避免 2PC 嘅性能代價）

```
┌─────────────────────────────────────────────────────────────┐
│                  Saga Pattern（編排式）                       │
│                                                              │
│  Probe → Pipeline → AI → Content → Search → Notification   │
│                                                              │
│  每一步產出事件，下一步消費。失敗時反向補償：                    │
│                                                              │
│  Step 1: Probe 採集成功                                      │
│  Step 2: Pipeline 清洗成功                                   │
│  Step 3: AI 處理成功                                         │
│  Step 4: Content 寫入成功                                    │
│  Step 5: ES 索引成功                                         │
│                                                              │
│  如果 Step 4 失敗：                                          │
│  → 補償 Step 3: 標記 AI 結果為 pending                       │
│  → 補償 Step 2: 將文章退回 cleaned 隊列                      │
│  → 不補償 Step 1: 原始數據保留（幂等重試）                    │
└─────────────────────────────────────────────────────────────┘
```

**具體實現**：

```python
# 用 Outbox Pattern 保證本地事務 + 事件發布嘅一致性
class ArticlePipeline:
    async def process_article(self, raw_article: RawArticle):
        # 1. 本地事務：寫入 outbox + 處理
        async with db.transaction():
            cleaned = await self.clean(raw_article)
            await db.outbox.insert({
                "topic": "tidxo.cleaned-articles",
                "key": cleaned.id,
                "payload": cleaned.dict(),
                "status": "pending"
            })
        
        # 2. Outbox relay 異步發送 Kafka（開獨立進程）
        # 3. 如果 Kafka 發送失敗，relay 會重試
        
    # 幂等消費：用 article_url_hash 做去重
    async def consume_cleaned(self, event: CleanedArticleEvent):
        if await self.already_processed(event.url_hash):
            return  # 幂等跳過
        await self.process(event)
        await self.mark_processed(event.url_hash)
```

**數據一致性分級**：

| 場景 | 一致性要求 | 實現方式 |
|------|-----------|---------|
| 文章發布 | 最終一致（秒級） | Kafka + Outbox |
| 用戶書籤 | 強一致 | 單體事務（PostgreSQL） |
| 搜索索引 | 最終一致（分鐘級） | Kafka → ES |
| 推送通知 | 最終一致（分鐘級） | Kafka + 重試 |
| 閱讀計數 | 最終一致（小時級） | Redis 計數 → 異步刷 DB |
| 用戶餘額/積分 | 強一致 | 單體事務 + 樂觀鎖 |

---

## 2. 可擴展性設計

### 2.1 水平擴展策略

#### 服務層擴展

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes HPA 策略                        │
│                                                              │
│  Service          │ Min │ Max │ CPU Target │ Memory Target  │
│  ─────────────────┼─────┼─────┼────────────┼─────────────── │
│  Content Service  │  2  │  10 │    70%     │     80%        │
│  Probe Service    │  1  │  20 │    60%     │     70%        │
│  Pipeline Service │  1  │  15 │    80%     │     85%        │
│  AI Service       │  1  │   5 │    50%     │     60%        │
│  User Service     │  2  │   8 │    70%     │     80%        │
│  Notification     │  1  │   5 │    60%     │     70%        │
│                                                              │
│  Probe Service 需要最多彈性：採集高峰（早7-9點）同低峰差10倍    │
│  AI Service 限制最嚴：LLM API 有 rate limit，唔能無限擴       │
└─────────────────────────────────────────────────────────────┘
```

**無狀態設計原則**：
- 所有服務唔存本地狀態，session 放 Redis
- 文件上傳直接寫 S3/MinIO，唔經過服務器本地磁盤
- 配置用 ConfigMap / Secret，唔硬編碼

#### API Gateway 擴展

```
                    ┌───────────────┐
                    │   DNS (Geo)   │
                    │  Route 53 /   │
                    │  CloudFlare   │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │   CDN Edge    │
                    │  (Cache Layer)│
                    └───────┬───────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
        ┌───────▼──┐ ┌─────▼────┐ ┌───▼──────┐
        │ Gateway  │ │ Gateway  │ │ Gateway  │
        │ Node 1   │ │ Node 2   │ │ Node 3   │
        │ (HK)     │ │ (HK)     │ │ (MO)     │
        └───────┬──┘ └─────┬────┘ └───┬──────┘
                │           │           │
                └───────────┼───────────┘
                            │
                    ┌───────▼───────┐
                    │   Internal    │
                    │   K8s Cluster │
                    └───────────────┘
```

### 2.2 數據庫分片/複製

#### PostgreSQL 分層策略

```
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL 拓撲結構                          │
│                                                              │
│  ┌─────────────────────────────────────────────┐            │
│  │           Primary (Write Master)             │            │
│  │           橫琴 Zone A                        │            │
│  └──────────┬──────────────┬────────────────────┘            │
│             │              │                                 │
│     ┌───────▼──────┐ ┌────▼────────┐                        │
│     │  Read Replica │ │ Read Replica│                        │
│     │  橫琴 Zone B  │ │  HK Zone    │                        │
│     │  (同步複製)   │ │ (異步複製)  │                        │
│     └──────────────┘ └─────────────┘                        │
│                                                              │
│  分庫策略（Phase 3 用戶量 > 10K 時）：                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  articles_db  │  │   users_db   │  │ analytics_db │      │
│  │  (按 source   │  │  (按 user_id │  │  (按時間     │      │
│  │   分片)       │  │   hash 分片) │  │   分區)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**文章表分片方案**：

```sql
-- 方案 A：按 source 分片（簡單，適合 Phase 1-2）
-- 每個新聞源嘅文章放同一個 shard
CREATE TABLE articles_shard_rthk (LIKE articles INCLUDING ALL);
CREATE TABLE articles_shard_scmp (LIKE articles INCLUDING ALL);
CREATE TABLE articles_shard_default (LIKE articles INCLUDING ALL);

-- 方案 B：按時間分區（適合日誌型數據）
CREATE TABLE articles (
    ...
) PARTITION BY RANGE (published_at);

CREATE TABLE articles_2026_q1 PARTITION OF articles
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE articles_2026_q2 PARTITION OF articles
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

-- 方案 C：按 hash 分片（Phase 3，用戶量 > 100K）
-- 用 Citus 或 PGShard
```

**Elasticsearch 分片策略**：

```json
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.sort.field": "published_at",
    "index.sort.order": "desc"
  }
}
// 按月份 rollover：tidxo-articles-2026-07
// 冷數據用 ILM 移到低成本 node
```

### 2.3 緩存策略（多層緩存）

```
┌─────────────────────────────────────────────────────────────┐
│                    多層緩存架構                               │
│                                                              │
│  L1: 客戶端緩存                                              │
│  ├── HTTP Cache-Control: max-age=300                         │
│  ├── Service Worker Cache (PWA)                              │
│  └── App 本地 SQLite / SharedPreferences                     │
│                                                              │
│  L2: CDN 邊緣緩存                                            │
│  ├── 靜態資源：圖片/CSS/JS → Cache-Control: max-age=86400    │
│  ├── API 響應：熱門文章列表 → Cache-Control: max-age=60      │
│  └── SSR 頁面：Next.js ISR → revalidate: 300                │
│                                                              │
│  L3: API Gateway 緩存                                        │
│  ├── Kong Response Caching Plugin                            │
│  ├── 按 URL + Query Param 做 key                             │
│  └── TTL: 30s - 5min（按 endpoint 配置）                     │
│                                                              │
│  L4: 應用層緩存（Redis）                                     │
│  ├── 熱門文章：article:{id} → TTL 10min                      │
│  ├── 用戶 Session：session:{user_id} → TTL 24h               │
│  ├── 分類列表：categories → TTL 1h                           │
│  ├── 搜索結果緩存：search:{hash} → TTL 5min                  │
│  └── 計數器：view_count:{article_id} → 異步刷 DB             │
│                                                              │
│  L5: 數據庫層                                                │
│  ├── PostgreSQL Buffer Pool (shared_buffers = 25% RAM)       │
│  ├── ES Filesystem Cache                                     │
│  └── Read Replica 分擔讀壓力                                 │
└─────────────────────────────────────────────────────────────┘
```

**緩存失效策略**：

```python
# Cache-Aside Pattern（最常用）
async def get_article(article_id: str):
    # 1. 查 Redis
    cached = await redis.get(f"article:{article_id}")
    if cached:
        return json.loads(cached)
    
    # 2. 查 DB
    article = await db.articles.get(article_id)
    if article:
        # 3. 寫回 Redis
        await redis.setex(
            f"article:{article_id}",
            600,  # TTL 10 分鐘
            json.dumps(article.dict())
        )
    return article

# Write-Through Pattern（寫入時更新緩存）
async def update_article(article_id: str, data: dict):
    async with db.transaction():
        article = await db.articles.update(article_id, data)
        await redis.setex(
            f"article:{article_id}",
            600,
            json.dumps(article.dict())
        )
        # 發布失效事件
        await kafka.send("cache-invalidation", {"key": f"article:{article_id}"})
    return article

# 緩存預熱（啟動時）
async def warmup_cache():
    # 預熱熱門文章（Top 100）
    hot_articles = await db.articles.get_hot(limit=100)
    for article in hot_articles:
        await redis.setex(f"article:{article.id}", 600, json.dumps(article.dict()))
    
    # 預熱分類列表
    categories = await db.categories.get_all()
    await redis.setex("categories", 3600, json.dumps(categories))
```

**緩存穿透/擊穿/雪崩防護**：

| 問題 | 防護方案 |
|------|---------|
| 緩存穿透（熱 key 過期） | 互斥鎖（singleflight）+ 永不過期 + 異步刷新 |
| 緩存擊穿（大量 key 同時過期） | TTL 加隨機偏移（±30s） |
| 緩存雪崩（Redis 整體掛咗） | 多層降級：Redis → 本地緩存 → DB |

---

## 3. 高可用方案

### 3.1 故障轉移機制

```
┌─────────────────────────────────────────────────────────────┐
│                    故障轉移架構                               │
│                                                              │
│  DNS Layer (CloudFlare / Route 53)                           │
│  ├── Health Check: 每 30s 探測                               │
│  ├── Failover TTL: 60s                                      │
│  └── Geo Routing: HK 用戶 → HK DC, MO 用戶 → MO DC         │
│                                                              │
│  ┌────────────────────┐    ┌────────────────────┐           │
│  │   橫琴 DC (Primary) │    │    HK DC (DR)      │           │
│  │                    │    │                    │           │
│  │  K8s Cluster       │    │  K8s Cluster       │           │
│  │  ├── All Services  │    │  ├── Core Services │           │
│  │  ├── PostgreSQL    │◄──►│  ├── PG Replica    │           │
│  │  │   (Primary)     │异步│  │   (Read-only)   │           │
│  │  ├── Redis         │複製│  ├── Redis Replica │           │
│  │  │   (Master)      │    │  │   (Read-only)   │           │
│  │  ├── Kafka         │    │  ├── ES Replica    │           │
│  │  └── ES (Primary)  │    │  └── MinIO Replica │           │
│  └────────────────────┘    └────────────────────┘           │
│                                                              │
│  RTO (Recovery Time Objective): < 5 分鐘                     │
│  RPO (Recovery Point Objective): < 1 分鐘                    │
└─────────────────────────────────────────────────────────────┘
```

**服務級別故障轉移**：

```python
# Circuit Breaker Pattern（熔斷器）
from tenacity import retry, stop_after_attempt, wait_exponential
import circuitbreaker

@circuitbreaker.CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=ServiceUnavailableError
)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_ai_service(article: Article):
    """調用 AI 服務，帶熔斷 + 重試"""
    try:
        return await ai_client.summarize(article)
    except ServiceUnavailableError:
        # 熔斷後返回降级結果
        return ArticleWithFallback(
            summary=article.content[:200],  # 用原文前 200 字做摘要
            translated=None  # 跳過翻譯
        )

# 每個服務間調用都要有：
# 1. Timeout（超時）
# 2. Retry（重試，指數退避）
# 3. Circuit Breaker（熔斷）
# 4. Fallback（降級）
# 5. Bulkhead（艙壁隔離）
```

**數據庫故障轉移**：

```
PostgreSQL:
├── Primary 掛了 → Patroni 自動 failover 到 Replica
├── Replica 掛了 → 從連接池移除，不影響寫入
└── 全掛 → 應用返回 503，等待恢復

Redis:
├── Master 掛了 → Redis Sentinel 自動 failover
├── 讀 Replica 掛了 → 應用降級到直接讀 DB
└── 全掛 → 應用用本地緩存（LruCache）兜底

Kafka:
├── Broker 掛了 → Producer/Consumer 自動重連到其他 Broker
├── Partition Leader 掛了 → 自動選舉新 Leader
└── 全掛 → 消息寫本地 WAL，恢復後重放
```

### 3.2 災難恢復計劃

```
┌─────────────────────────────────────────────────────────────┐
│                    災難恢復分級                                │
│                                                              │
│  Level 1: 單服務故障（自動恢復）                              │
│  ├── K8s 自動重啟 Pod                                       │
│  ├── 耗時：< 30 秒                                           │
│  └── 影響：該服務短暫不可用                                  │
│                                                              │
│  Level 2: 單節點故障（自動轉移）                              │
│  ├── K8s 調度到其他 Node                                    │
│  ├── DB failover 到 Replica                                 │
│  ├── 耗時：< 2 分鐘                                          │
│  └── 影響：部分請求失敗，自動重試                            │
│                                                              │
│  Level 3: 單 AZ 故障（跨 AZ 容災）                           │
│  ├── K8s Node 跨 AZ 分佈                                    │
│  ├── DB 跨 AZ 同步複製                                      │
│  ├── 耗時：< 5 分鐘                                          │
│  └── 影響：延遲增加，容量降級                                │
│                                                              │
│  Level 4: 整 DC 故障（跨 DC 容災）                           │
│  ├── DNS 切換到 DR DC                                       │
│  ├── DB 切換到異步 Replica                                  │
│  ├── 耗時：< 15 分鐘                                         │
│  └── 影響：部分最新數據可能丟失（RPO < 1min）                │
│                                                              │
│  Level 5: 區域性災難（備份恢復）                              │
│  ├── 從異地備份恢復                                         │
│  ├── 耗時：< 4 小時                                          │
│  └── 影響：數據恢復到最近備份點                              │
└─────────────────────────────────────────────────────────────┘
```

**備份策略**：

```yaml
# 備份計劃
backups:
  postgresql:
    full: "每日 02:00 UTC+8"
    incremental: "WAL 持續歸檔到 S3"
    retention: "30 日"
    cross_region: "異地複製到 HK S3"
    
  redis:
    rdb: "每 6 小時"
    aof: "持續開啟"
    retention: "7 日"
    
  elasticsearch:
    snapshot: "每日 03:00 UTC+8"
    retention: "14 日"
    
  minio_s3:
    replication: "跨區域實時複製"
    versioning: "開啟"
    
  kafka:
    retention: "7 日消息保留"
    mirror: "MirrorMaker 2 異步複製到 DR"
```

### 3.3 監控告警體系

```
┌─────────────────────────────────────────────────────────────┐
│                    監控體系（Three Pillars）                  │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │    Metrics      │  │     Logs        │  │   Traces    │ │
│  │  (Prometheus +  │  │   (ELK Stack)   │  │ (Jaeger /   │ │
│  │   Grafana)      │  │                 │  │  Tempo)     │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘ │
│           │                    │                   │        │
│           └────────────────────┼───────────────────┘        │
│                                │                            │
│                    ┌───────────▼───────────┐                │
│                    │    AlertManager        │                │
│                    │  ├── 分級告警          │                │
│                    │  ├── 靜默/抑制         │                │
│                    │  └── 路由（值班表）     │                │
│                    └───────────┬───────────┘                │
│                                │                            │
│              ┌─────────────────┼─────────────────┐          │
│              │                 │                 │          │
│       ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐   │
│       │  釘釘/飛書  │  │   PagerDuty │  │   Email     │   │
│       │  (P1/P2)    │  │   (P1)      │  │  (P3/P4)   │   │
│       └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**告警分級**：

| 級別 | 定義 | 響應時間 | 通知方式 | 例子 |
|------|------|---------|---------|------|
| **P1 - Critical** | 服務完全不可用 | < 5 分鐘 | 電話 + IM + PagerDuty | DB 主庫掛了、全部 Pod CrashLoop |
| **P2 - High** | 核心功能降級 | < 15 分鐘 | IM + PagerDuty | API P99 > 2s、Probe 成功率 < 80% |
| **P3 - Medium** | 非核心功能異常 | < 1 小時 | IM + Email | AI 服務延遲高、搜索索引延遲 |
| **P4 - Low** | 預警/趨勢 | < 4 小時 | Email | 磁盤使用 > 70%、CPU 趨勢上升 |

**核心監控指標**：

```yaml
# Prometheus Rules
groups:
  - name: tidxo_core
    rules:
      # 服務可用性
      - alert: ServiceDown
        expr: up{job=~"tidxo-.*"} == 0
        for: 1m
        labels: { severity: P1 }
        
      # API 延遲
      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 2
        for: 5m
        labels: { severity: P2 }
        
      # 錯誤率
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
        for: 3m
        labels: { severity: P2 }
        
      # 探針成功率
      - alert: ProbeSuccessRateLow
        expr: rate(probe_success_total[10m]) / rate(probe_attempts_total[10m]) < 0.80
        for: 10m
        labels: { severity: P2 }
        
      # Kafka 消費延遲
      - alert: KafkaConsumerLag
        expr: kafka_consumer_lag > 10000
        for: 5m
        labels: { severity: P3 }
        
      # 數據庫連接池
      - alert: DBConnectionPoolExhausted
        expr: pg_stat_activity_count / pg_settings_max_connections > 0.85
        for: 3m
        labels: { severity: P2 }
        
      # Redis 內存
      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
        for: 5m
        labels: { severity: P3 }
```

---

## 4. 性能優化

### 4.1 瓶頸分析

```
┌─────────────────────────────────────────────────────────────┐
│                    潛在瓶頸熱點圖                             │
│                                                              │
│  風險等級：🔴 高  🟡 中  🟢 低                               │
│                                                              │
│  組件              │ 瓶頸風險 │ 原因              │ 對策     │
│  ──────────────────┼─────────┼──────────────────┼───────── │
│  Probe Service     │  🔴     │ 外部網站響應慢    │ 異步+超時│
│  AI Service (LLM)  │  🔴     │ API 延遲 2-30s   │ 異步+降級│
│  Pipeline 去重     │  🟡     │ CPU 密集計算      │ GPU/獨立 │
│  PostgreSQL 寫入   │  🟡     │ 高併發插入        │ 批量+分片│
│  ES 搜索          │  🟡     │ 複雜查詢慢         │ 索引優化 │
│  Redis            │  🟢     │ 通常夠快          │ 監控內存  │
│  API Gateway      │  🟢     │ Kong 性能足夠      │ 水平擴展 │
└─────────────────────────────────────────────────────────────┘
```

**關鍵瓶頸深度分析**：

#### 瓶頸 1：Probe Service — 外部依賴不可控

```
問題：
- 新聞源響應時間 100ms - 10s 不等
- 部分源有 rate limit / 反爬
- 源站掛了會拖死採集線程

解決方案：
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Scheduler│───▶│  Worker  │───▶│  Queue   │
│ (調度器) │    │  Pool    │    │ (Kafka)  │
│          │    │ (per-src)│    │          │
└──────────┘    └──────────┘    └──────────┘

1. 每個源獨立 Worker Pool，互不影響
2. 超時控制：connect=5s, read=15s, total=30s
3. 尊重 rate limit：用令牌桶算法
4. 失敗重試：指數退避，最多 3 次
5. 代理池：被封時切換 IP
```

#### 瓶頸 2：AI Service — LLM 調用延遲

```
問題：
- GPT-4 響應 2-10s
- Rate limit: 60 RPM (Tier 1)
- 成本高：$0.03/1K tokens

解決方案（分級處理）：

Level 1: 即時處理（< 1s）
├── 規則摘要：提取首段 + 關鍵句
├── 本地小模型：Llama 7B 做簡單分類
└── 預計算：熱門文章提前處理

Level 2: 近線處理（1-30s）
├── LLM API：GPT-4 / Claude
├── 批量處理：5 篇一批，減少 API 調用
└── 優先隊列：Breaking News 優先

Level 3: 離線處理（分鐘級）
├── 批量翻譯：非熱門文章
├── 深度分析：長文報告
└── 定時任務：凌晨批量處理

┌──────────┐    ┌──────────┐    ┌──────────┐
│ Priority │───▶│  Batch   │───▶│   LLM    │
│  Queue   │    │  Manager │    │  Router   │
│          │    │          │    │          │
│ P0: 即時 │    │ 5篇/批   │    │ GPT-4    │
│ P1: 高   │    │ 10篇/批  │    │ Claude   │
│ P2: 普通 │    │ 50篇/批  │    │ Llama    │
│ P3: 低   │    │          │    │ 規則引擎  │
└──────────┘    └──────────┘    └──────────┘
```

### 4.2 異步處理優化

```python
# 全異步 Pipeline 設計
import asyncio
from asyncio import TaskGroup

class AsyncPipeline:
    """全異步處理管道"""
    
    async def process(self, raw_article: RawArticle):
        # 1. 並行執行獨立任務
        async with TaskGroup() as tg:
            clean_task = tg.create_task(self.clean(raw_article))
            dedup_task = tg.create_task(self.check_duplicate(raw_article))
        
        cleaned = clean_task.result()
        is_dup = dedup_task.result()
        
        if is_dup:
            return None  # 跳過重複
        
        # 2. 並行執行 AI 任務
        async with TaskGroup() as tg:
            summary_task = tg.create_task(self.ai.summarize(cleaned))
            translate_task = tg.create_task(self.ai.translate(cleaned))
            tag_task = tg.create_task(self.ai.extract_tags(cleaned))
        
        # 3. 組裝結果
        article = ProcessedArticle(
            **cleaned.dict(),
            summary=summary_task.result(),
            translation=translate_task.result(),
            tags=tag_task.result()
        )
        
        # 4. 異步寫入（不阻塞）
        await self.publish("tidxo.ai-processed", article)
        return article

# Celery 異步任務（適合非即時場景）
from celery import Celery

celery_app = Celery('tidxo', broker='redis://redis:6379/0')

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='10/m'  # 限制每分鐘 10 個
)
def generate_daily_digest(self):
    """每日早報生成"""
    articles = get_hot_articles(limit=10)
    digest = llm.generate_digest(articles)
    send_to_all_users(digest)
```

### 4.3 CDN 策略

```
┌─────────────────────────────────────────────────────────────┐
│                    CDN 分層策略                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Edge CDN (CloudFlare / AWS CloudFront)             │    │
│  │                                                      │    │
│  │  靜態資源（命中率 > 99%）：                            │    │
│  │  ├── /static/* → Cache-Control: max-age=31536000     │    │
│  │  ├── /images/* → Cache-Control: max-age=86400        │    │
│  │  └── /_next/static/* → Immutable, max-age=31536000   │    │
│  │                                                      │    │
│  │  動態內容（命中率 > 60%）：                            │    │
│  │  ├── /api/v1/articles → Cache-Control: s-maxage=60   │    │
│  │  ├── /api/v1/categories → s-maxage=300               │    │
│  │  └── /api/v1/articles/{id} → s-maxage=120            │    │
│  │                                                      │    │
│  │  不緩存（ personalised ）：                            │    │
│  │  ├── /api/v1/users/* → Cache-Control: no-cache       │    │
│  │  ├── /api/v1/bookmarks/* → no-cache                  │    │
│  │  └── /api/v1/feed/* → no-cache（但有 edge compute）   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Image CDN（圖片優化）                               │    │
│  │                                                      │    │
│  │  原始圖片 → MinIO/S3                                 │    │
│  │       │                                              │    │
│  │       ▼                                              │    │
│  │  CDN Edge (CloudFlare Images / imgix)                │    │
│  │  ├── 自動格式轉換：WebP / AVIF                       │    │
│  │  ├── 響應式尺寸：?w=400&h=300&fit=cover              │    │
│  │  ├── 質量優化：?quality=80                            │    │
│  │  └── Lazy loading：loading="lazy"                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  SSR / ISR（Next.js）                                │    │
│  │                                                      │    │
│  │  首頁：ISR revalidate=300（5分鐘重新生成）            │    │
│  │  文章詳情：ISR revalidate=60（1分鐘）                 │    │
│  │  分類頁：SSG + 客戶端更新                             │    │
│  │  搜索頁：CSR（純客戶端渲染）                          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 安全架構

### 5.1 API 安全（認證/授權/加密）

```
┌─────────────────────────────────────────────────────────────┐
│                    API 安全分層                               │
│                                                              │
│  Layer 1: 網絡層                                             │
│  ├── DDoS 防護（CloudFlare / AWS Shield）                    │
│  ├── WAF（Web Application Firewall）                        │
│  ├── IP 黑名單 / 白名單                                      │
│  └── TLS 1.3 強制（HSTS preload）                           │
│                                                              │
│  Layer 2: 認證層                                             │
│  ├── JWT (RS256) — Access Token (15min) + Refresh Token (7d)│
│  ├── OAuth 2.0 + PKCE — Google / Apple / WeChat 登錄        │
│  ├── API Key — B2B 客戶                                     │
│  └── Rate Limiting — 100 req/min (anonymous), 1000 (authed) │
│                                                              │
│  Layer 3: 授權層                                             │
│  ├── RBAC（Role-Based Access Control）                       │
│  │   ├── anonymous: 只讀公開內容                              │
│  │   ├── user: 個人功能（書籤/偏好）                         │
│  │   ├── premium: 高級功能（深度分析）                        │
│  │   ├── admin: 管理後台                                    │
│  │   └── service: 服務間調用                                 │
│  ├── ABAC（Attribute-Based）— 精細控制                       │
│  └── Resource Ownership — 只能操作自己嘅資源                  │
│                                                              │
│  Layer 4: 數據層                                             │
│  ├── Input Validation（FastAPI Pydantic 自動校驗）           │
│  ├── SQL Injection 防護（ORM parameterized queries）          │
│  ├── XSS 防護（CSP headers + 輸出編碼）                      │
│  └── CSRF 防護（SameSite cookies + CSRF token）              │
└─────────────────────────────────────────────────────────────┘
```

**JWT 認證流程**：

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Client  │                    │  Auth    │                    │  API     │
│          │                    │  Service │                    │  Server  │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  1. POST /auth/login          │                               │
     │  {email, password}            │                               │
     │──────────────────────────────▶│                               │
     │                               │                               │
     │  2. Return tokens             │                               │
     │  {access_token (15min),       │                               │
     │   refresh_token (7d)}         │                               │
     │◄──────────────────────────────│                               │
     │                               │                               │
     │  3. GET /api/articles         │                               │
     │  Authorization: Bearer <jwt>  │                               │
     │──────────────────────────────────────────────────────────────▶│
     │                               │                               │
     │                               │  4. Verify JWT (RS256)        │
     │                               │  5. Check permissions         │
     │                               │  6. Process request           │
     │                               │                               │
     │  7. Response                  │                               │
     │◄──────────────────────────────────────────────────────────────│
     │                               │                               │
     │  8. Token expired (15min)     │                               │
     │  POST /auth/refresh           │                               │
     │  {refresh_token}              │                               │
     │──────────────────────────────▶│                               │
     │                               │                               │
     │  9. New access_token          │                               │
     │◄──────────────────────────────│                               │
```

**Token 安全存儲**：

```
Web (PWA):
├── Access Token: Memory only (JS variable), 唔存 localStorage
├── Refresh Token: httpOnly + Secure + SameSite=Strict cookie
└── 登出時清除所有 token

Mobile (iOS/Android):
├── Access Token: Keychain (iOS) / EncryptedSharedPreferences (Android)
├── Refresh Token: 同上
└── 支持生物識別解鎖

B2B API:
├── API Key: Header (X-API-Key)
├── IP 白名單
└── 請求簽名 (HMAC-SHA256)
```

### 5.2 數據安全（存儲/傳輸）

```
┌─────────────────────────────────────────────────────────────┐
│                    數據安全矩陣                               │
│                                                              │
│  數據類型          │ 存儲加密        │ 傳輸加密      │ 備份加密 │
│  ──────────────────┼────────────────┼──────────────┼──────── │
│  用戶密碼          │ bcrypt (cost=12)│ HTTPS only   │ N/A     │
│  用戶 Email        │ AES-256-GCM    │ TLS 1.3      │ 加密    │
│  閱讀歷史          │ 明文（可匿名化）│ TLS 1.3      │ 加密    │
│  文章內容          │ 明文           │ TLS 1.3      │ 加密    │
│  API Keys          │ AES-256-GCM    │ TLS 1.3      │ 加密    │
│  Session           │ Redis 加密     │ TLS 1.3      │ N/A     │
│  日誌              │ 脫敏處理       │ TLS 1.3      │ 加密    │
│                                                              │
│  加密密鑰管理：AWS KMS / HashiCorp Vault                     │
│  密鑰輪轉：每 90 日自動輪轉                                  │
└─────────────────────────────────────────────────────────────┘
```

**敏感數據處理**：

```python
# 密碼存儲
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__rounds=12  # cost factor
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hash: str) -> bool:
    return pwd_context.verify(password, hash)

# 敏感字段加密（Email、手機號等）
from cryptography.fernet import Fernet

class EncryptedField:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()

# 日誌脫敏
import logging

class SensitiveDataFilter(logging.Filter):
    PATTERNS = [
        (r'password["\s:=]+\S+', 'password=***'),
        (r'token["\s:=]+\S+', 'token=***'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', '<email_redacted>'),
    ]
    
    def filter(self, record):
        for pattern, replacement in self.PATTERNS:
            record.msg = re.sub(pattern, replacement, record.msg)
        return True
```

### 5.3 合規要求（GDPR、個人資料私隱條例）

```
┌─────────────────────────────────────────────────────────────┐
│                    合規框架（港澳市場）                        │
│                                                              │
│  適用法規：                                                   │
│  ├── 澳門《個人資料保護法》（第8/2005號法律）                 │
│  ├── 香港《個人資料（私隱）條例》（第486章）                  │
│  ├── GDPR（如有歐盟用戶）                                    │
│  └── 大灣區數據跨境流動規定                                  │
│                                                              │
│  核心原則：                                                   │
│  ├── 1. 數據最小化：只收集必要數據                            │
│  ├── 2. 目的限制：數據只用於聲明嘅目的                        │
│  ├── 3. 存儲限制：保留期不超過必要                            │
│  ├── 4. 用戶權利：訪問/更正/刪除/可攜帶                      │
│  └── 5. 安全保障：技術+組織措施保護數據                      │
└─────────────────────────────────────────────────────────────┘
```

**用戶權利實現**：

```python
# 數據訪問權（Right of Access）
@router.get("/users/me/data-export")
async def export_user_data(user: User = Depends(get_current_user)):
    """导出用户所有个人数据（GDPR Article 15）"""
    return {
        "profile": user.dict(),
        "bookmarks": await db.bookmarks.get_by_user(user.id),
        "reading_history": await db.history.get_by_user(user.id),
        "preferences": await db.preferences.get(user.id),
        "exported_at": datetime.utcnow().isoformat()
    }

# 被遺忘權（Right to Erasure / 刪除權）
@router.delete("/users/me/account")
async def delete_user_account(user: User = Depends(get_current_user)):
    """删除用户账户及所有个人数据（GDPR Article 17）"""
    # 1. 軟刪除用戶（保留 30 日可恢復）
    await db.users.soft_delete(user.id)
    
    # 2. 匿名化閱讀歷史
    await db.history.anonymize(user_id=user.id)
    
    # 3. 刪除書籤
    await db.bookmarks.delete_by_user(user.id)
    
    # 4. 刪除第三方服務數據
    await analytics.delete_user_data(user.id)
    await notification.unsubscribe_all(user.id)
    
    # 5. 排程永久刪除（30 日後）
    await celery.send_task(
        "permanent_delete_user",
        args=[user.id],
        countdown=30 * 24 * 3600  # 30 天後
    )
    
    return {"message": "Account scheduled for deletion in 30 days"}

# 數據可攜帶權（Right to Data Portability）
@router.get("/users/me/data-portable")
async def export_portable_data(user: User = Depends(get_current_user)):
    """以 JSON 格式导出可携带数据"""
    return {
        "format": "json",
        "data": {
            "profile": user.dict(exclude={"password_hash"}),
            "bookmarks": await db.bookmarks.get_by_user(user.id),
        }
    }
```

**Cookie / 同意管理**：

```
┌─────────────────────────────────────────────────────────────┐
│                    Cookie 同意管理                            │
│                                                              │
│  首次訪問 → 顯示 Cookie Banner                               │
│  ├── Necessary（必要）：默認開啟，不可關閉                    │
│  │   ├── session_id（認證）                                  │
│  │   └── csrf_token（安全）                                  │
│  │                                                          │
│  ├── Analytics（分析）：需用戶同意                            │
│  │   ├── _ga（Google Analytics）                             │
│  │   └── mixpanel（用戶行為）                                │
│  │                                                          │
│  └── Marketing（營銷）：需用戶同意                            │
│      └── 推送通知 token                                      │
│                                                              │
│  同意記錄：存儲到 consent_log 表，保留 2 年                   │
│  撤回同意：用戶可隨時在設置中關閉                              │
└─────────────────────────────────────────────────────────────┘
```

**數據跨境流動**：

```
⚠️ 重要：港澳數據跨境限制

澳門：
├── 個人資料出境需通知用戶
├── 目的地需有「足夠保護水平」
├── 中國大陸：需要特別說明同保障措施
└── 建議：澳門用戶數據存澳門/橫琴服務器

香港：
├── 沒有嚴格嘅跨境限制（第33條尚未生效）
├── 但需要告知用戶數據存儲位置
└── 建議：香港用戶數據存香港或澳門服務器

大灣區：
├── 遵循《大灣區數據跨境流動標準合同》
├── 需要數據保護影響評估（DPIA）
└── 建議：設立獨立嘅大灣區數據治理流程
```

---

## 6. 總結與優先級建議

### 6.1 優先級矩陣

```
┌─────────────────────────────────────────────────────────────┐
│                    實施優先級                                 │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Phase 1（MVP，必做）                                 │    │
│  │                                                      │    │
│  │ ✅ Monolith-ish 架構（快速驗證）                      │    │
│  │ ✅ JWT 認證 + RBAC                                    │    │
│  │ ✅ Redis 緩存（L4）                                   │    │
│  │ ✅ PostgreSQL 主從複製                                │    │
│  │ ✅ 基礎監控（Prometheus + Grafana）                    │    │
│  │ ✅ HTTPS + HSTS                                      │    │
│  │ ✅ 隱私政策 + Cookie 同意                             │    │
│  │ ✅ 備份策略（每日全量 + WAL 增量）                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Phase 2（功能完善，建議做）                           │    │
│  │                                                      │    │
│  │ 🔲 Kafka 事件總線                                    │    │
│  │ 🔲 微服務拆分（Content / Probe / AI）                 │    │
│  │ 🔲 CDN 整合（CloudFlare）                             │    │
│  │ 🔲 Circuit Breaker + Fallback                        │    │
│  │ 🔲 多層緩存（CDN + Gateway + Redis）                  │    │
│  │ 🔲 告警分級 + 值班制度                                │    │
│  │ 🔲 數據脫敏 + 審計日誌                                │    │
│  │ 🔲 用戶數據導出/刪除功能                              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Phase 3（規模化，按需做）                             │    │
│  │                                                      │    │
│  │ 🔲 完整微服務 + Service Mesh                          │    │
│  │ 🔲 數據庫分片（Citus）                                │    │
│  │ 🔲 跨 DC 容災                                        │    │
│  │ 🔲 分佈式追蹤（Jaeger）                               │    │
│  │ 🔲 自動擴容（HPA + KEDA）                             │    │
│  │ 🔲 GDPR 完整合規                                      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 關鍵建議

1. **Phase 1 唔好過度設計**：Monolith 先跑通，驗證產品市場契合再拆分
2. **事件驅動係核心**：Kafka/Redis Stream 從 Phase 1 就要引入，唔好用同步調用串聯所有服務
3. **安全從 Day 1**：JWT + HTTPS + 備份加密 + 隱私政策，呢啲唔可以遲
4. **監控先行**：無監控嘅系統等於盲飛，Phase 1 就要有 Prometheus + Grafana
5. **預留擴展點**：數據庫 schema 設計要考慮分片，API 要考慮版本控制

### 6.3 架構決策記錄（ADR）建議

| 決策 | 選擇 | 替代方案 | 理由 |
|------|------|---------|------|
| 消息隊列 | Kafka (Phase 2) | RabbitMQ / Redis Stream | 高吞吐、消息持久化、重放能力 |
| 服務間通訊 | gRPC (內部) + REST (外部) | 純 REST | gRPC 性能好、強類型、支持 streaming |
| 數據庫 | PostgreSQL + Citus (Phase 3) | MySQL / CockroachDB | JSON 支持好、生態成熟、港澳團隊熟悉 |
| 緩存 | Redis Cluster | Memcached | 數據結構豐富、支持持久化、pub/sub |
| 搜索 | Elasticsearch | Meilisearch / Typesense | 功能最全、中文分詞好、社區活躍 |
| 容器編排 | Kubernetes | Docker Swarm | 業界標準、生態完善、雲廠商支持好 |
| CI/CD | GitHub Actions + ArgoCD | Jenkins / GitLab CI | GitOps 流程、K8s 原生整合 |

---

**審查結論**：

PROJECT_PLAN 整體方向正確，微服務 + 事件驅動嘅架構適合呢個項目。主要建議：

1. **Phase 1 保持簡單**，唔好一開始就拆太細
2. **事件驅動從 early stage 引入**，避免後期重構
3. **安全合規從 Day 1 開始**，港澳市場對私隱保護要求高
4. **監控告警係必需品**，唔係奢侈品
5. **預留水平擴展能力**，但唔好過度投資

整體評分：**7.5/10** — 規劃完善，執行時注意唔好 over-engineer。

---

*審查完成 — 2026-07-26*
