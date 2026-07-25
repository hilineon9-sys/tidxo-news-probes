# Tidxo 智能資訊聚合平台 - 項目規劃文檔

## 1. 項目願景與核心價值

### 1.1 產品定位
**一站式智能資訊聚合平台**，專注港澳大灣區市場，提供：
- 多源新聞聚合與智能分類
- 雙語（中/英）內容生成
- 個性化資訊推送
- 深度數據分析與洞察

### 1.2 核心價值主張
- **資訊無縫**：整合分散嘅新聞源，一站式獲取
- **智能過濾**：AI 驅動嘅內容分類、去重、摘要
- **雙語無障礙**：自動中英雙語轉換
- **本地深耕**：專注港澳市場，貼合本地需求

### 1.3 目標用戶群
**Phase 1（0-6個月）**：
- 港澳媒體從業者
- 政策研究者
- 商業決策者
- 大學生/研究生

**Phase 2（6-18個月）**：
- 普通新聞消費者
- 投資者/金融從業者
- 旅遊/商務旅客

**Phase 3（18-36個月）**：
- 大灣區跨城用戶
- 企業客戶（B2B）
- 教育機構

---

## 2. 系統架構設計

### 2.1 整體架構（Microservices + Event-Driven）

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ iOS App  │  │Android   │  │Web PWA   │  │API       │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Kong/Nginx)                  │
│  - Rate Limiting  - Auth  - Load Balancing  - Caching       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer (Microservices)           │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Probe Service│  │ Aggregation  │  │ AI Service   │     │
│  │ (採集服務)    │  │ Service      │  │ (NLP/LLM)    │     │
│  │              │  │ (聚合服務)    │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ User Service │  │ Notification │  │ Analytics    │     │
│  │ (用戶服務)    │  │ Service      │  │ Service      │     │
│  │              │  │ (通知服務)    │  │ (分析服務)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PostgreSQL│  │Elastic-  │  │ Redis    │  │ S3/Minio │   │
│  │(Metadata)│  │search    │  │ (Cache)  │  │ (Media)  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Kubernetes│  │Prometheus│  │ ELK Stack│  │ CI/CD    │   │
│  │(K8s)     │  │+ Grafana │  │ (Logs)   │  │ (GitHub) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心模組詳細設計

#### 2.2.1 資訊探針採集模組 (Probe Module)
**職責**：從各大新聞源採集原始數據

**技術棧**：
- Python 3.11+
- httpx (異步 HTTP)
- BeautifulSoup4 / lxml (HTML 解析)
- feedparser (RSS)
- Scrapy (可選，複雜場景)

**架構**：
```
probes/
├── base.py              # 探針基類
├── models.py            # 統一數據模型
├── registry.py          # 自動註冊機制
├── runner.py            # 執行器
└── sources/             # 新聞源探針
    ├── rthk.py
    ├── scmp.py
    ├── macau_daily.py
    └── ...
```

**關鍵特性**：
- 高兼容性：新源只需實現 `fetch_raw()` + `parse()`
- 自動發現：放入 `sources/` 自動註冊
- 錯誤容忍：單個源失敗不影響整體
- 速率控制：尊重 robots.txt，避免被封

**數據模型**：
```python
class Article(BaseModel):
    title: str
    url: str
    source: str
    published: Optional[datetime]
    summary: Optional[str]
    content: Optional[str]
    author: Optional[str]
    category: Optional[str]
    language: str  # zh / en
    image_url: Optional[str]
    tags: list[str]
```

#### 2.2.2 數據清洗聚類模組 (Aggregation Module)
**職責**：清洗、去重、分類、聚類

**技術棧**：
- Python + pandas (數據處理)
- scikit-learn (文本分類)
- sentence-transformers (語義相似度)
- Celery + Redis (異步任務隊列)

**處理流程**：
```
Raw Articles
    ↓
[1. 數據清洗]
    - 去除 HTML tags
    - 標準化編碼
    - 提取純文本
    ↓
[2. 去重檢測]
    - SimHash / MinHash
    - 語義相似度 > 0.85 → 標記為重複
    ↓
[3. 自動分類]
    - 本地/大中華/國際/財經/體育
    - 基於標題+內容的多標籤分類
    ↓
[4. 聚類 grouping]
    - 同一事件嘅多篇報導聚合
    - 生成事件時間線
    ↓
Cleaned & Clustered Articles
```

#### 2.2.3 雲端 AI 雙語內容生成模組 (AI Module)
**職責**：智能摘要、雙語轉換、內容增強

**技術棧**：
- LLM API (OpenAI GPT-4 / Claude / 本地部署 Llama)
- LangChain (LLM 應用框架)
- Hugging Face Transformers (本地模型)

**功能**：
1. **智能摘要**：生成 100-200 字摘要
2. **雙語轉換**：中→英 / 英→中 自動翻譯
3. **標題優化**：生成更具吸引力嘅標題
4. **關鍵詞提取**：自動生成 tags
5. **情感分析**：標記正面/中性/負面

**Prompt Engineering**：
```python
SUMMARY_PROMPT = """
你係一個專業嘅新聞編輯。請為以下新聞生成簡潔嘅摘要（100-150字）：

標題：{title}
內容：{content}

要求：
1. 保留關鍵信息
2. 客觀中立
3. 語言流暢
"""
```

#### 2.2.4 用戶服務模組 (User Service)
**職責**：用戶管理、個性化、偏好設置

**技術棧**：
- FastAPI (API)
- JWT (認證)
- PostgreSQL (用戶數據)
- Redis (session cache)

**功能**：
- 註冊/登錄（Email + OAuth）
- 興趣標籤設置
- 閱讀歷史
- 收藏/書籤
- 推送偏好

**個性化算法**：
```python
def recommend_articles(user, candidate_articles):
    # 1. 基於用戶興趣標籤過濾
    tagged = [a for a in candidate_articles 
              if any(t in user.interests for t in a.tags)]
    
    # 2. 基於閱讀歷史的協同過濾
    similar_users = find_similar_users(user)
    recommended = get_articles_read_by(similar_users)
    
    # 3. 排序：相關性 + 時效性 + 熱門度
    scored = score_articles(tagged + recommended, user)
    return sorted(scored, key=lambda x: x.score, reverse=True)
```

#### 2.2.5 通知服務模組 (Notification Service)
**職責**：多渠道推送

**技術棧**：
- Firebase Cloud Messaging (FCM) - 移動推送
- Apple Push Notification Service (APNs) - iOS
- WebSocket - 實時通知
- Email (SendGrid / AWS SES)

**推送策略**：
- **Breaking News**：即時推送
- **Daily Digest**：每日早報（8:00 AM）
- **Weekly Summary**：每週精選
- **Personalized**：基於用戶興趣

#### 2.2.6 分析服務模組 (Analytics Service)
**職責**：數據分析、用戶行為追蹤

**技術棧**：
- Mixpanel / Amplitude（用戶行為分析）
- Google Analytics（Web）
- 自定義 Dashboard（Grafana）

**關鍵指標**：
- DAU / MAU（日/月活躍用戶）
- 留存率（7日/30日）
- 平均閱讀時長
- 推送點擊率
- 分享率

---

## 3. 技術規格

### 3.1 後端技術棧

| 組件 | 技術選型 | 理由 |
|------|---------|------|
| API Framework | FastAPI | 高性能、異步、自動文檔 |
| Database | PostgreSQL 15 | 穩定、JSON 支持、全文搜索 |
| Search Engine | Elasticsearch 8 | 全文搜索、聚合分析 |
| Cache | Redis 7 | 高性能緩存、pub/sub |
| Task Queue | Celery + Redis | 異步任務、定時任務 |
| Message Queue | RabbitMQ / Kafka | 事件驅動（Phase 2） |
| Object Storage | MinIO / S3 | 圖片、媒體文件 |
| Container | Docker + K8s | 可擴展、易部署 |
| CI/CD | GitHub Actions | 自動化測試、部署 |

### 3.2 前端技術棧

| 平台 | 技術選型 | 理由 |
|------|---------|------|
| iOS | Swift + SwiftUI | 原生性能、最佳體驗 |
| Android | Kotlin + Jetpack Compose | 原生性能、現代 UI |
| Web | Next.js + React | SSR、SEO、PWA 支持 |
| State Management | Zustand / Redux Toolkit | 簡單、高效 |
| API Client | Axios + React Query | 緩存、重試、樂觀更新 |

### 3.3 API 設計規範

**RESTful API**：
```
GET    /api/v1/articles          # 獲取文章列表
GET    /api/v1/articles/{id}     # 獲取文章詳情
POST   /api/v1/articles/search   # 搜索文章
GET    /api/v1/categories        # 獲取分類列表
GET    /api/v1/sources           # 獲取新聞源列表

POST   /api/v1/users/register    # 註冊
POST   /api/v1/users/login       # 登錄
GET    /api/v1/users/profile     # 獲取用戶資料
PUT    /api/v1/users/preferences # 更新偏好設置

POST   /api/v1/bookmarks         # 添加書籤
DELETE /api/v1/bookmarks/{id}    # 刪除書籤
GET    /api/v1/bookmarks         # 獲取書籤列表
```

**Response Format**：
```json
{
  "success": true,
  "data": {
    "articles": [...],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100
    }
  },
  "meta": {
    "request_id": "abc123",
    "timestamp": "2026-07-26T01:56:15Z"
  }
}
```

**Error Handling**：
```json
{
  "success": false,
  "error": {
    "code": "ARTICLE_NOT_FOUND",
    "message": "Article with id '123' not found",
    "details": {}
  }
}
```

### 3.4 數據庫設計

**核心表結構**：

```sql
-- 文章表
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    url VARCHAR(1000) NOT NULL UNIQUE,
    summary TEXT,
    content TEXT,
    author VARCHAR(200),
    category VARCHAR(100),
    language VARCHAR(10) DEFAULT 'zh',
    image_url VARCHAR(1000),
    published_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT NOW(),
    tags TEXT[],
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 用戶表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(200),
    avatar_url VARCHAR(1000),
    interests TEXT[],
    language_preference VARCHAR(10) DEFAULT 'zh',
    push_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 書籤表
CREATE TABLE bookmarks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, article_id)
);

-- 閱讀歷史表
CREATE TABLE reading_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    read_at TIMESTAMP DEFAULT NOW(),
    read_duration INTEGER -- 秒
);

-- 索引
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_category ON articles(category);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_tags ON articles USING GIN(tags);
CREATE INDEX idx_articles_search ON articles USING GIN(to_tsvector('chinese', title || ' ' || COALESCE(summary, '')));
```

### 3.5 性能指標

| 指標 | 目標值 | 測量方法 |
|------|--------|---------|
| API 響應時間 | < 200ms (P95) | Prometheus + Grafana |
| 探針採集成功率 | > 95% | 自定義 metrics |
| 系統可用性 | 99.9% | Uptime monitoring |
| 並發用戶支持 | 10,000 | Load testing |
| 數據庫查詢 | < 50ms (P95) | Query profiling |
| 緩存命中率 | > 80% | Redis metrics |

---

## 4. 用戶黏結策略

### 4.1 核心策略

#### 4.1.1 個性化體驗
- **智能推薦**：基於閱讀歷史、興趣標籤
- **個性化推送**：只推送用戶感興趣嘅內容
- **自定義首頁**：用戶可選擇顯示嘅分類/源

#### 4.1.2 社交互動
- **評論系統**：允許用戶討論
- **分享功能**：一鍵分享到 WhatsApp/WeChat/Facebook
- **熱門討論**：顯示最受關注嘅新聞

#### 4.1.3 遊戲化元素
- **閱讀積分**：每日閱讀獲得積分
- **成就系統**：解鎖徽章（如「連續7日閱讀」）
- **排行榜**：活躍用戶展示

#### 4.1.4 獨家內容
- **深度分析**：AI 生成嘅專題報告
- **數據可視化**：互動圖表、時間線
- **專家觀點**：邀請本地專家撰寫評論

#### 4.1.5 離線功能
- **離線閱讀**：預先下載感興趣嘅文章
- **離線書籤**：無網絡時仍可訪問書籤

### 4.2 推送策略

**避免推送疲勞**：
- 每日最多 5 條推送
- 用戶可設置「免打擾」時段
- 基於重要性分級推送

**推送內容**：
- Breaking News（即時）
- 用戶關注分類嘅熱門新聞
- 每日早報（8:00 AM）
- 每週精選（週日 10:00 AM）

### 4.3 留存機制

**Day 1-7（新手期）**：
- 引導式 onboarding
- 推薦熱門新聞
- 鼓勵設置興趣標籤

**Day 7-30（成長期）**：
- 推送個性化內容
- 解鎖成就徽章
- 邀請參與評論

**Day 30+（成熟期）**：
- 獨家內容
- 專家互動
- 社區活動

---

## 5. 項目路線圖

### Phase 1：MVP（0-3個月）
**目標**：驗證核心功能，獲取首批用戶

**功能**：
- ✅ 探針採集模組（已完成）
- 🔲 數據清洗聚類（基礎版）
- 🔲 Web PWA（最小功能集）
- 🔲 用戶註冊/登錄
- 🔲 文章列表/詳情
- 🔲 基礎搜索

**技術重點**：
- 搭建基礎架構
- 實現核心 API
- 部署到橫琴服務器

**用戶目標**：100 註冊用戶

### Phase 2：功能完善（3-6個月）
**目標**：提升用戶體驗，增加黏性

**功能**：
- 🔲 AI 摘要生成
- 🔲 雙語翻譯
- 🔲 個性化推薦
- 🔲 推送通知
- 🔲 書籤/收藏
- 🔲 iOS/Android App（Beta）

**技術重點**：
- 整合 LLM API
- 優化推薦算法
- 性能優化

**用戶目標**：1,000 註冊用戶

### Phase 3：增長（6-12個月）
**目標**：規模化增長，建立品牌

**功能**：
- 🔲 社交功能（評論、分享）
- 🔲 深度分析報告
- 🔲 數據可視化
- 🔲 遊戲化元素
- 🔲 B2B API 服務

**技術重點**：
- 微服務拆分
- 大數據分析
- 高可用架構

**用戶目標**：10,000 註冊用戶

### Phase 4：商業化（12-24個月）
**目標**：實現營收，可持續發展

**功能**：
- 🔲 訂閱制（Premium）
- 🔲 廣告系統
- 🔲 企業服務
- 🔲 數據授權

**技術重點**：
- 支付整合
- 廣告平台
- 數據安全

**營收目標**：月營收 MOP 50,000

---

## 6. 資源需求

### 6.1 人力資源

**Phase 1（MVP）**：
- 全端開發 × 1（你）
- AI/ML 顧問 × 0.5（兼職）
- UI/UX 設計 × 0.5（兼職）

**Phase 2**：
- 後端開發 × 1
- 前端開發 × 1
- AI 工程師 × 1
- 產品經理 × 0.5

**Phase 3**：
- 完整團隊（5-8人）

### 6.2 基礎設施成本（月度估算）

**Phase 1**：
- 服務器（橫琴）：MOP 500
- 域名 + SSL：MOP 100
- LLM API：MOP 500
- **總計：~MOP 1,100/月**

**Phase 2**：
- 服務器：MOP 2,000
- LLM API：MOP 3,000
- 第三方服務：MOP 1,000
- **總計：~MOP 6,000/月**

**Phase 3**：
- 服務器：MOP 8,000
- LLM API：MOP 10,000
- 第三方服務：MOP 5,000
- **總計：~MOP 23,000/月**

### 6.3 開發時間估算

**Phase 1（MVP）**：
- 探針模組：2 週（已完成）
- 數據清洗：2 週
- API 開發：3 週
- Web 前端：3 週
- 測試 + 部署：2 週
- **總計：12 週**

**Phase 2**：
- AI 整合：4 週
- 推薦系統：3 週
- 移動 App：6 週
- 推送系統：2 週
- **總計：15 週**

---

## 7. 風險與應對

### 7.1 技術風險

| 風險 | 影響 | 應對策略 |
|------|------|---------|
| 新聞源封鎖 | 高 | 多源冗餘、 respectful crawling |
| LLM API 成本 | 中 | 本地模型 + 雲 API 混合 |
| 性能瓶頸 | 中 | 緩存、CDN、水平擴展 |
| 數據安全 | 高 | 加密、權限控制、審計 |

### 7.2 商業風險

| 風險 | 影響 | 應對策略 |
|------|------|---------|
| 用戶增長慢 | 高 | 精準營銷、KOL 合作 |
| 營收不及預期 | 高 | 多元營收模式、成本控制 |
| 競爭對手 | 中 | 差異化定位、快速迭代 |
| 政策變化 | 中 | 合規審查、政府關係 |

---

## 8. 成功指標

### 8.1 產品指標
- DAU / MAU > 20%
- 7日留存率 > 40%
- 30日留存率 > 20%
- 平均閱讀時長 > 5 分鐘

### 8.2 技術指標
- 系統可用性 > 99.9%
- API 響應時間 < 200ms (P95)
- 探針成功率 > 95%
- 錯誤率 < 0.1%

### 8.3 商業指標
- Phase 1：100 註冊用戶
- Phase 2：1,000 註冊用戶
- Phase 3：10,000 註冊用戶
- Phase 4：月營收 MOP 50,000

---

## 9. 下一步行動

### 即刻行動（本週）
1. ✅ 完成探針模組框架
2. 🔲 修復剩餘探針（TVB、星島）
3. 🔲 添加更多新聞源（香港01、明報）
4. 🔲 搭建數據清洗模組原型
5. 🔲 設計數據庫 schema

### 短期行動（1個月內）
1. 🔲 完成數據清洗聚類模組
2. 🔲 搭建 FastAPI 後端
3. 🔲 實現核心 API
4. 🔲 開發 Web PWA 前端
5. 🔲 部署到橫琴服務器

### 中期行動（3個月內）
1. 🔲 完成 MVP 所有功能
2. 🔲 內部測試 + 修復 bug
3. 🔲 邀請首批用戶測試
4. 🔲 收集反饋 + 迭代
5. 🔲 準備 Phase 2 規劃

---

## 10. 附錄

### 10.1 參考資源
- [FastAPI 文檔](https://fastapi.tiangolo.com/)
- [Celery 文檔](https://docs.celeryq.dev/)
- [React Native 文檔](https://reactnative.dev/)
- [LangChain 文檔](https://python.langchain.com/)

### 10.2 術語表
- **探針（Probe）**：新聞源採集模組
- **聚合（Aggregation）**：數據清洗、去重、分類
- **PWA**：Progressive Web App（漸進式 Web 應用）
- **LLM**：Large Language Model（大型語言模型）

---

**文檔版本**：v1.0  
**最後更新**：2026-07-26  
**作者**：Tidxo Team
