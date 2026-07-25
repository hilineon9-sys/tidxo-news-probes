# Tidxo 前端技術審查報告

**審查日期**：2026-07-26  
**審查人**：資深前端開發工程師  
**文檔版本**：v1.0

---

## 執行摘要

本報告針對 Tidxo 智能資訊聚合平台嘅前端技術方案進行全面審查，涵蓋技術選型、UI/UX 設計、性能優化、狀態管理同開發效率五個維度。整體嚟講，項目規劃文檔中嘅技術選型合理，但喺跨平台策略、性能優化同開發效率方面仍有改進空間。

**核心建議**：
1. 考慮採用 React Native 統一 iOS/Android 開發，降低維護成本
2. Web 端採用 Next.js 14 App Router + React Server Components
3. 建立統一嘅設計系統，確保多端一致性
4. 實施分層緩存策略，優化首屏加載

---

## 1. 技術選型分析

### 1.1 iOS: SwiftUI vs UIKit

**現狀評估**：項目已選擇 Swift + SwiftUI

**建議**：**維持 SwiftUI 選擇，但需要考慮兼容性**

**分析**：
- ✅ **優勢**：
  - 聲明式語法，開發效率高
  - 自動適配深色模式、動態字體
  - 與 Apple 最新技術（Widget、Live Activities）整合良好
  - 預覽功能（Preview）加速 UI 開發

- ⚠️ **風險**：
  - 需要 iOS 15+（2021年發布），覆蓋率約 95%
  - 部分複雜 UI（自定義轉場動畫）實現較難
  - 第三方庫生態不如 UIKit 成熟

**代碼示例 - SwiftUI 文章列表**：
```swift
import SwiftUI

struct ArticleListView: View {
    @StateObject private var viewModel = ArticleListViewModel()
    @Environment(\.scenePhase) private var scenePhase
    
    var body: some View {
        NavigationStack {
            List {
                ForEach(viewModel.articles) { article in
                    NavigationLink(value: article) {
                        ArticleCardView(article: article)
                    }
                }
                
                if viewModel.isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                }
            }
            .listStyle(.plain)
            .refreshable {
                await viewModel.refresh()
            }
            .navigationTitle("新聞")
            .navigationDestination(for: Article.self) { article in
                ArticleDetailView(article: article)
            }
            .task {
                await viewModel.loadArticles()
            }
        }
    }
}

struct ArticleCardView: View {
    let article: Article
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // 分類標籤
            if let category = article.category {
                Text(category)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.accentColor.opacity(0.2))
                    .clipShape(Capsule())
            }
            
            // 標題
            Text(article.title)
                .font(.headline)
                .lineLimit(2)
            
            // 摘要
            if let summary = article.summary {
                Text(summary)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(3)
            }
            
            // 元信息
            HStack {
                Text(article.source)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Text(article.publishedAt, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 8)
    }
}
```

**替代方案 - UIKit + SwiftUI 混合**：
如果目標用戶包括 iOS 13/14 用戶（約 5%），可以考慮：
```swift
// 使用 @available 檢查
if #available(iOS 15.0, *) {
    SwiftUIArticleListView()
} else {
    UIKitArticleListView() // 傳統 UIKit 實現
}
```

### 1.2 Android: Jetpack Compose vs XML

**現狀評估**：項目已選擇 Kotlin + Jetpack Compose

**建議**：**強烈支持 Jetpack Compose 選擇**

**分析**：
- ✅ **優勢**：
  - 聲明式 UI，與 SwiftUI 概念一致，降低學習成本
  - 更少嘅代碼量（相比 XML + Activity/Fragment）
  - 更好嘅性能（直接渲染，跳過 View 系統）
  - Material 3 支持完善

- ⚠️ **注意事項**：
  - 需要 Android 5.0+（API 21，覆蓋率 99%+）
  - 部分舊設備性能可能不如原生 View

**代碼示例 - Jetpack Compose 文章列表**：
```kotlin
@Composable
fun ArticleListScreen(
    viewModel: ArticleListViewModel = hiltViewModel(),
    onArticleClick: (Article) -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("新聞") },
                actions = {
                    IconButton(onClick = { /* 搜索 */ }) {
                        Icon(Icons.Default.Search, contentDescription = "搜索")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(uiState.articles) { article ->
                ArticleCard(
                    article = article,
                    onClick = { onArticleClick(article) }
                )
            }
            
            if (uiState.isLoading) {
                item {
                    CircularProgressIndicator(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp)
                    )
                }
            }
        }
        
        // 下拉刷新
        if (uiState.isRefreshing) {
            // 使用 PullRefreshIndicator
        }
    }
    
    LaunchedEffect(Unit) {
        viewModel.loadArticles()
    }
}

@Composable
fun ArticleCard(
    article: Article,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // 分類標籤
            article.category?.let { category ->
                Surface(
                    color = MaterialTheme.colorScheme.primaryContainer,
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        text = category,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
            }
            
            // 標題
            Text(
                text = article.title,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            
            // 摘要
            article.summary?.let { summary ->
                Text(
                    text = summary,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis
                )
            }
            
            // 元信息
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = article.source,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                
                Text(
                    text = article.publishedAt.toRelativeTimeString(),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
```

### 1.3 Web: Next.js vs Nuxt.js vs Remix

**現狀評估**：項目已選擇 Next.js + React

**建議**：**強烈支持 Next.js 選擇，建議升級到 Next.js 14 App Router**

**分析**：

| 框架 | SEO | 性能 | 學習曲線 | 生態 | 推薦度 |
|------|-----|------|----------|------|--------|
| Next.js 14 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ 首選 |
| Nuxt.js 3 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 適合 Vue 團隊 |
| Remix | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 適合表單密集應用 |

**Next.js 14 優勢**：
- **React Server Components**：減少客戶端 JS 體積
- **App Router**：更直觀嘅路由結構
- **Streaming SSR**：更快嘅首屏加載
- **PWA 支持**：配合 `next-pwa` 實現離線功能
- **Vercel/自託管**：靈活部署

**代碼示例 - Next.js 14 App Router**：
```typescript
// app/articles/page.tsx (Server Component)
import { Suspense } from 'react'
import { ArticleList } from '@/components/ArticleList'
import { ArticleListSkeleton } from '@/components/skeletons'

export default async function ArticlesPage({
  searchParams
}: {
  searchParams: { category?: string; page?: string }
}) {
  const category = searchParams.category || 'all'
  const page = parseInt(searchParams.page || '1')

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">最新新聞</h1>
      
      <Suspense fallback={<ArticleListSkeleton />}>
        <ArticleList category={category} page={page} />
      </Suspense>
    </div>
  )
}

// components/ArticleList.tsx (Server Component)
import { fetchArticles } from '@/lib/api'
import { ArticleCard } from './ArticleCard'

export async function ArticleList({ 
  category, 
  page 
}: { 
  category: string
  page: number 
}) {
  const articles = await fetchArticles({ category, page })

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {articles.map((article) => (
        <ArticleCard key={article.id} article={article} />
      ))}
    </div>
  )
}

// components/ArticleCard.tsx (Client Component)
'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Article } from '@/types'

export function ArticleCard({ article }: { article: Article }) {
  return (
    <article className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow">
      {article.imageUrl && (
        <Image
          src={article.imageUrl}
          alt={article.title}
          width={400}
          height={200}
          className="w-full h-48 object-cover"
          priority={false}
        />
      )}
      
      <div className="p-4">
        {article.category && (
          <span className="inline-block px-2 py-1 text-xs font-semibold bg-blue-100 text-blue-800 rounded">
            {article.category}
          </span>
        )}
        
        <Link href={`/articles/${article.id}`}>
          <h2 className="text-xl font-bold mt-2 hover:text-blue-600">
            {article.title}
          </h2>
        </Link>
        
        {article.summary && (
          <p className="text-gray-600 mt-2 line-clamp-3">
            {article.summary}
          </p>
        )}
        
        <div className="flex justify-between items-center mt-4 text-sm text-gray-500">
          <span>{article.source}</span>
          <time>{new Date(article.publishedAt).toLocaleDateString('zh-HK')}</time>
        </div>
      </div>
    </article>
  )
}
```

**PWA 配置**：
```javascript
// next.config.js
const withPWA = require('next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
})

module.exports = withPWA({
  // 其他配置
})
```

### 1.4 跨平台方案可行性分析

**方案對比**：

| 方案 | 性能 | 開發效率 | 原生體驗 | 維護成本 | 推薦度 |
|------|------|----------|----------|----------|--------|
| React Native | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ 推薦 |
| Flutter | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⚠️ 需 Dart 團隊 |
| 原生雙端 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ❌ 成本高 |

**建議：採用 React Native（Expo）**

**理由**：
1. **代碼複用**：與 Web 端共享 React 生態，業務邏輯可複用 60-70%
2. **開發效率**：Hot Reload、Expo Go 快速預覽
3. **原生模組**：需要時可編寫原生模組（Swift/Kotlin）
4. **團隊技能**：React 團隊可快速上手

**代碼示例 - React Native (Expo)**：
```typescript
// App.tsx
import { NavigationContainer } from '@react-navigation/native'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import HomeScreen from './screens/HomeScreen'
import SearchScreen from './screens/SearchScreen'
import BookmarksScreen from './screens/BookmarksScreen'
import ProfileScreen from './screens/ProfileScreen'

const Tab = createBottomTabNavigator()
const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NavigationContainer>
        <Tab.Navigator>
          <Tab.Screen 
            name="首頁" 
            component={HomeScreen} 
            options={{
              tabBarIcon: ({ focused }) => (
                <Icon name="home" color={focused ? '#007AFF' : '#8E8E93'} />
              )
            }}
          />
          <Tab.Screen 
            name="搜索" 
            component={SearchScreen}
            options={{
              tabBarIcon: ({ focused }) => (
                <Icon name="search" color={focused ? '#007AFF' : '#8E8E93'} />
              )
            }}
          />
          <Tab.Screen 
            name="書籤" 
            component={BookmarksScreen}
            options={{
              tabBarIcon: ({ focused }) => (
                <Icon name="bookmark" color={focused ? '#007AFF' : '#8E8E93'} />
              )
            }}
          />
          <Tab.Screen 
            name="我的" 
            component={ProfileScreen}
            options={{
              tabBarIcon: ({ focused }) => (
                <Icon name="person" color={focused ? '#007AFF' : '#8E8E93'} />
              )
            }}
          />
        </Tab.Navigator>
      </NavigationContainer>
    </QueryClientProvider>
  )
}

// screens/HomeScreen.tsx
import { FlatList, RefreshControl, StyleSheet } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import { fetchArticles } from '../api/articles'
import ArticleCard from '../components/ArticleCard'

export default function HomeScreen() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['articles'],
    queryFn: fetchArticles,
  })

  return (
    <FlatList
      data={data?.articles || []}
      keyExtractor={(item) => item.id.toString()}
      renderItem={({ item }) => <ArticleCard article={item} />}
      refreshControl={
        <RefreshControl 
          refreshing={isRefetching} 
          onRefresh={refetch}
          tintColor="#007AFF"
        />
      }
      contentContainerStyle={styles.container}
    />
  )
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
})
```

**Expo 配置**：
```json
// app.json
{
  "expo": {
    "name": "Tidxo",
    "slug": "tidxo",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#ffffff"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.tidxo.app"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#ffffff"
      },
      "package": "com.tidxo.app"
    },
    "web": {
      "favicon": "./assets/favicon.png"
    }
  }
}
```

---

## 2. UI/UX 設計建議

### 2.1 信息架構設計

**建議採用三層信息架構**：

```
L1: 導航層（Tab Bar / Bottom Navigation）
├── 首頁（最新/推薦）
├── 搜索（全文搜索 + 篩選）
├── 書籤（收藏文章）
└── 我的（個人設置）

L2: 分類層（首頁內）
├── 全部
├── 本地新聞
├── 大中華
├── 國際
├── 財經
├── 體育
└── 自定義分類

L3: 內容層
├── 文章詳情
├── 相關文章
├── 評論區
└── 分享功能
```

**信息架構原則**：
1. **3-click 規則**：用戶最多 3 次點擊到達目標內容
2. **渐进式披露**：先展示摘要，詳情頁再展開完整內容
3. **個性化入口**：根據用戶興趣調整首頁分類排序

### 2.2 導航模式

**推薦：混合導航模式**

**Web 端**：
```
┌─────────────────────────────────────┐
│  Logo    [分類導航]    [搜索] [用戶] │  ← 頂部導航
├─────────────────────────────────────┤
│                                     │
│  [側邊欄]     [主內容區]            │  ← 可摺疊側邊欄
│  - 分類                           │
│  - 熱門                           │
│  - 書籤                           │
│                                     │
└─────────────────────────────────────┘
```

**移動端**：
```
┌─────────────────────┐
│  [返回] 標題  [操作] │  ← 頂部 App Bar
├─────────────────────┤
│                     │
│    [內容區]         │
│                     │
├─────────────────────┤
│ 🏠  🔍  🔖  👤     │  ← 底部 Tab Bar
└─────────────────────┘
```

**代碼示例 - Web 端響應式導航**：
```typescript
// components/Navigation.tsx
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Menu, X, Search, User, Bookmark } from 'lucide-react'
import { cn } from '@/lib/utils'

const categories = [
  { name: '全部', slug: 'all' },
  { name: '本地', slug: 'local' },
  { name: '大中華', slug: 'china' },
  { name: '國際', slug: 'international' },
  { name: '財經', slug: 'finance' },
  { name: '體育', slug: 'sports' },
]

export function Navigation() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const pathname = usePathname()

  return (
    <>
      {/* 桌面端頂部導航 */}
      <nav className="hidden md:flex items-center justify-between px-6 py-4 border-b">
        <Link href="/" className="text-2xl font-bold">
          Tidxo
        </Link>

        <div className="flex items-center gap-6">
          {categories.map((category) => (
            <Link
              key={category.slug}
              href={`/articles?category=${category.slug}`}
              className={cn(
                'text-sm font-medium transition-colors hover:text-blue-600',
                pathname.includes(category.slug)
                  ? 'text-blue-600'
                  : 'text-gray-600'
              )}
            >
              {category.name}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-4">
          <button className="p-2 hover:bg-gray-100 rounded-full">
            <Search className="w-5 h-5" />
          </button>
          <button className="p-2 hover:bg-gray-100 rounded-full">
            <Bookmark className="w-5 h-5" />
          </button>
          <button className="p-2 hover:bg-gray-100 rounded-full">
            <User className="w-5 h-5" />
          </button>
        </div>
      </nav>

      {/* 移動端頂部導航 */}
      <nav className="md:hidden flex items-center justify-between px-4 py-3 border-b">
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="p-2"
        >
          {isMobileMenuOpen ? <X /> : <Menu />}
        </button>
        <Link href="/" className="text-xl font-bold">
          Tidxo
        </Link>
        <button className="p-2">
          <Search className="w-5 h-5" />
        </button>
      </nav>

      {/* 移動端側邊菜單 */}
      {isMobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50 bg-white pt-16">
          <div className="flex flex-col gap-4 p-6">
            {categories.map((category) => (
              <Link
                key={category.slug}
                href={`/articles?category=${category.slug}`}
                onClick={() => setIsMobileMenuOpen(false)}
                className="text-lg font-medium py-2 border-b"
              >
                {category.name}
              </Link>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
```

### 2.3 響應式設計策略

**斷點系統**：
```css
/* tailwind.config.js */
module.exports = {
  theme: {
    screens: {
      'sm': '640px',   // 手機橫屏
      'md': '768px',   // 平板直屏
      'lg': '1024px',  // 平板橫屏/小筆記本
      'xl': '1280px',  // 桌面顯示器
      '2xl': '1536px', // 大螢幕
    },
  },
}
```

**響應式佈局示例**：
```typescript
// components/ArticleGrid.tsx
export function ArticleGrid({ articles }: { articles: Article[] }) {
  return (
    <div className="
      grid 
      gap-4 
      grid-cols-1        /* 手機：1列 */
      sm:grid-cols-2     /* 手機橫屏：2列 */
      md:grid-cols-2     /* 平板：2列 */
      lg:grid-cols-3     /* 桌面：3列 */
      xl:grid-cols-4     /* 大螢幕：4列 */
    ">
      {articles.map((article) => (
        <ArticleCard key={article.id} article={article} />
      ))}
    </div>
  )
}
```

**圖片響應式**：
```typescript
// components/ResponsiveImage.tsx
import Image from 'next/image'

export function ResponsiveImage({ src, alt }: { src: string; alt: string }) {
  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes="
        (max-width: 640px) 100vw,
        (max-width: 1024px) 50vw,
        33vw
      "
      className="object-cover"
      priority={false}
    />
  )
}
```

### 2.4 無障礙設計（Accessibility）

**核心原則**：
1. **語義化 HTML**：使用 `<article>`, `<nav>`, `<main>` 等語義標籤
2. **鍵盤導航**：所有交互元素可通過 Tab 鍵訪問
3. **屏幕閱讀器**：提供 `aria-label` 同 `alt` 文本
4. **色彩對比**：WCAG AA 標準（4.5:1）
5. **動態字體**：支持用戶系統字體大小設置

**代碼示例**：
```typescript
// components/AccessibleButton.tsx
interface ButtonProps {
  children: React.ReactNode
  onClick: () => void
  'aria-label'?: string
  disabled?: boolean
}

export function AccessibleButton({ 
  children, 
  onClick, 
  'aria-label': ariaLabel,
  disabled 
}: ButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-disabled={disabled}
      className="
        px-4 py-2 
        bg-blue-600 text-white 
        rounded-md 
        hover:bg-blue-700 
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        disabled:opacity-50 disabled:cursor-not-allowed
        transition-colors
      "
    >
      {children}
    </button>
  )
}

// 使用示例
<AccessibleButton 
  onClick={handleBookmark}
  aria-label={`將「${article.title}」加入書籤`}
>
  <BookmarkIcon className="w-5 h-5" />
</AccessibleButton>
```

**跳過導航鏈接**：
```html
<!-- 允許鍵盤用戶跳過導航直接到主內容 -->
<a 
  href="#main-content" 
  className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4"
>
  跳過導航
</a>

<main id="main-content" tabIndex={-1}>
  {/* 主內容 */}
</main>
```

---

## 3. 性能優化策略

### 3.1 首屏加載優化

**目標**：Largest Contentful Paint (LCP) < 2.5 秒

**策略**：

1. **代碼分割（Code Splitting）**：
```typescript
// 動態導入組件
import dynamic from 'next/dynamic'

const ArticleDetail = dynamic(
  () => import('@/components/ArticleDetail'),
  { 
    loading: () => <ArticleDetailSkeleton />,
    ssr: false // 如果不需要 SSR
  }
)
```

2. **字體優化**：
```typescript
// app/layout.tsx
import { Inter } from 'next/font/google'

const inter = Inter({ 
  subsets: ['latin', 'chinese-traditional'],
  display: 'swap', // 避免 FOIT
})

export default function RootLayout({ children }) {
  return (
    <html lang="zh-HK" className={inter.className}>
      <body>{children}</body>
    </html>
  )
}
```

3. **預加載關鍵資源**：
```typescript
// components/ArticleCard.tsx
import Link from 'next/link'

export function ArticleCard({ article }: { article: Article }) {
  return (
    <Link href={`/articles/${article.id}`} prefetch={true}>
      {/* 當卡片進入視口時自動預加載 */}
      <article>...</article>
    </Link>
  )
}
```

4. **Critical CSS 內聯**：
```javascript
// next.config.js
module.exports = {
  experimental: {
    optimizeCss: true, // 自動提取關鍵 CSS
  },
}
```

### 3.2 圖片/媒體優化

**策略**：

1. **Next.js Image 組件**（自動優化）：
```typescript
import Image from 'next/image'

<Image
  src={article.imageUrl}
  alt={article.title}
  width={800}
  height={400}
  placeholder="blur" // 模糊佔位符
  blurDataURL="data:image/jpeg;base64,/9j/4AAQSkZJRg..." // 低質量預覽
  quality={75} // 壓縮質量
  sizes="(max-width: 768px) 100vw, 50vw"
/>
```

2. **懶加載非關鍵圖片**：
```typescript
<Image
  src={article.imageUrl}
  alt=""
  loading="lazy" // 瀏覽器原生懶加載
  {...props}
/>
```

3. **WebP 格式自動轉換**：
Next.js Image 組件自動為支持的瀏覽器提供 WebP 格式。

4. **視頻優化**：
```typescript
// 使用 <video> 標籤而非 GIF
<video 
  autoPlay 
  loop 
  muted 
  playsInline
  poster="/video-poster.jpg"
>
  <source src="/video.webm" type="video/webm" />
  <source src="/video.mp4" type="video/mp4" />
</video>
```

### 3.3 離線緩存策略

**PWA Service Worker 配置**：
```javascript
// public/sw.js
const CACHE_NAME = 'tidxo-v1'
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
]

// 安裝時緩存靜態資源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS)
    })
  )
})

// 請求攔截：網絡優先，失敗時返回緩存
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // 克隆響應並緩存
        const responseClone = response.clone()
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseClone)
        })
        return response
      })
      .catch(() => {
        // 網絡失敗時返回緩存
        return caches.match(event.request)
      })
  )
})

// API 請求緩存策略
self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/articles')) {
    event.respondWith(
      caches.open('api-cache').then((cache) => {
        return cache.match(event.request).then((cachedResponse) => {
          const fetchPromise = fetch(event.request).then((networkResponse) => {
            // 緩存最新數據（Stale-While-Revalidate）
            cache.put(event.request, networkResponse.clone())
            return networkResponse
          })
          
          // 返回緩存（如果有），否則等待網絡請求
          return cachedResponse || fetchPromise
        })
      })
    )
  }
})
```

**客戶端離線存儲**：
```typescript
// lib/offlineStorage.ts
import { openDB } from 'idb'

const DB_NAME = 'tidxo-offline'
const STORE_NAME = 'articles'

export async function saveArticleForOffline(article: Article) {
  const db = await openDB(DB_NAME, 1, {
    upgrade(db) {
      db.createObjectStore(STORE_NAME, { keyPath: 'id' })
    },
  })
  
  await db.put(STORE_NAME, article)
}

export async function getOfflineArticles(): Promise<Article[]> {
  const db = await openDB(DB_NAME, 1)
  return await db.getAll(STORE_NAME)
}

// 使用示例
export function useOfflineArticles() {
  const [articles, setArticles] = useState<Article[]>([])
  
  useEffect(() => {
    if (!navigator.onLine) {
      getOfflineArticles().then(setArticles)
    }
  }, [])
  
  return articles
}
```

### 3.4 内存管理

**Web 端**：
```typescript
// 避免内存洩漏：清理定時器同事件監聽器
useEffect(() => {
  const interval = setInterval(() => {
    // 定期檢查更新
  }, 60000)
  
  const handleVisibilityChange = () => {
    if (document.hidden) {
      clearInterval(interval)
    }
  }
  
  document.addEventListener('visibilitychange', handleVisibilityChange)
  
  return () => {
    clearInterval(interval)
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }
}, [])

// 虛擬化長列表（避免渲染過多 DOM 節點）
import { useVirtualizer } from '@tanstack/react-virtual'

function VirtualArticleList({ articles }: { articles: Article[] }) {
  const parentRef = useRef<HTMLDivElement>(null)
  
  const virtualizer = useVirtualizer({
    count: articles.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 200, // 預估每個項目高度
  })
  
  return (
    <div ref={parentRef} style={{ height: '100vh', overflow: 'auto' }}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const article = articles[virtualRow.index]
          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <ArticleCard article={article} />
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

**移動端（React Native）**：
```typescript
// 使用 FlatList 自動優化内存
<FlatList
  data={articles}
  renderItem={({ item }) => <ArticleCard article={item} />}
  keyExtractor={(item) => item.id.toString()}
  initialNumToRender={10} // 初始渲染數量
  maxToRenderPerBatch={5} // 每批渲染數量
  windowSize={5} // 窗口大小（減少内存佔用）
  removeClippedSubviews={true} // 移除不可見視圖
/>
```

---

## 4. 狀態管理方案

### 4.1 全局狀態方案

**建議：Zustand（輕量） + React Query（服務端狀態）**

**理由**：
- **Zustand**：體積小（< 1KB）、API 簡單、無需 Provider
- **React Query**：專門處理服務端狀態、自動緩存/重試/樂觀更新

**代碼示例**：
```typescript
// stores/userStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UserState {
  user: User | null
  isAuthenticated: boolean
  login: (user: User) => void
  logout: () => void
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      login: (user) => set({ user, isAuthenticated: true }),
      logout: () => set({ user: null, isAuthenticated: false }),
    }),
    {
      name: 'user-storage', // localStorage key
    }
  )
)

// 使用示例
function ProfileButton() {
  const { user, logout } = useUserStore()
  
  if (!user) return <LoginButton />
  
  return (
    <div>
      <span>{user.name}</span>
      <button onClick={logout}>登出</button>
    </div>
  )
}
```

### 4.2 服務端狀態管理（React Query）

**完整配置**：
```typescript
// lib/react-query.ts
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5分鐘內數據視為新鮮
      cacheTime: 1000 * 60 * 60 * 24, // 緩存24小時
      retry: 3, // 失敗重試3次
      refetchOnWindowFocus: false, // 窗口獲得焦點時不自動重新請求
    },
  },
})

// hooks/useArticles.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchArticles, bookmarkArticle } from '@/lib/api'

export function useArticles(category: string, page: number) {
  return useQuery({
    queryKey: ['articles', category, page],
    queryFn: () => fetchArticles({ category, page }),
  })
}

export function useBookmarkArticle() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: bookmarkArticle,
    // 樂觀更新
    onMutate: async (articleId) => {
      // 取消當前的 refetch
      await queryClient.cancelQueries({ queryKey: ['bookmarks'] })
      
      // 保存之前的數據
      const previousBookmarks = queryClient.getQueryData(['bookmarks'])
      
      // 樂觀更新緩存
      queryClient.setQueryData(['bookmarks'], (old: any) => [
        ...old,
        { articleId, createdAt: new Date() }
      ])
      
      // 返回之前的數據用於回滾
      return { previousBookmarks }
    },
    // 失敗時回滾
    onError: (err, articleId, context) => {
      queryClient.setQueryData(
        ['bookmarks'],
        context?.previousBookmarks
      )
    },
    // 成功後重新獲取
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] })
    },
  })
}

// 使用示例
function ArticleList() {
  const { data, isLoading, error } = useArticles('all', 1)
  
  if (isLoading) return <Skeleton />
  if (error) return <ErrorMessage error={error} />
  
  return (
    <div>
      {data.articles.map((article) => (
        <ArticleCard key={article.id} article={article} />
      ))}
    </div>
  )
}
```

### 4.3 本地存儲策略

**分層存儲方案**：

| 數據類型 | 存儲方式 | 過期時間 | 示例 |
|---------|---------|---------|------|
| 用戶認證 | localStorage | 永久 | JWT token |
| 用戶偏好 | localStorage | 永久 | 主題、語言 |
| API 響應 | IndexedDB | 24小時 | 文章列表 |
| 離線文章 | IndexedDB | 手動管理 | 書籤文章 |
| 臨時狀態 | sessionStorage | 會話 | 表單數據 |

**代碼示例**：
```typescript
// lib/storage.ts
import { openDB, IDBPDatabase } from 'idb'

const DB_NAME = 'tidxo-storage'
const DB_VERSION = 1

// IndexedDB 初始化
async function getDB(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      // 文章緩存
      if (!db.objectStoreNames.contains('articles')) {
        db.createObjectStore('articles', { keyPath: 'id' })
      }
      
      // 用戶偏好
      if (!db.objectStoreNames.contains('preferences')) {
        db.createObjectStore('preferences', { keyPath: 'key' })
      }
    },
  })
}

// 緩存文章
export async function cacheArticle(article: Article) {
  const db = await getDB()
  await db.put('articles', {
    ...article,
    cachedAt: Date.now(),
  })
}

// 獲取緩存文章（檢查過期）
export async function getCachedArticle(id: number): Promise<Article | null> {
  const db = await getDB()
  const cached = await db.get('articles', id)
  
  if (!cached) return null
  
  // 檢查是否過期（24小時）
  const isExpired = Date.now() - cached.cachedAt > 24 * 60 * 60 * 1000
  if (isExpired) {
    await db.delete('articles', id)
    return null
  }
  
  return cached
}

// 清理過期緩存
export async function clearExpiredCache() {
  const db = await getDB()
  const tx = db.transaction('articles', 'readwrite')
  const store = tx.objectStore('articles')
  
  const allArticles = await store.getAll()
  const now = Date.now()
  
  for (const article of allArticles) {
    if (now - article.cachedAt > 24 * 60 * 60 * 1000) {
      await store.delete(article.id)
    }
  }
  
  await tx.done
}
```

---

## 5. 開發效率提升

### 5.1 組件庫選擇

**建議：shadcn/ui（Web） + React Native Paper（移動端）**

**shadcn/ui 優勢**：
- 基於 Radix UI + Tailwind CSS
- 可定制性強（代碼直接複製到項目）
- 無運行時開銷
- 無障礙支持完善

**安裝配置**：
```bash
# Web 端
npx shadcn-ui@latest init

# 添加常用組件
npx shadcn-ui@latest add button card input dialog
```

**使用示例**：
```typescript
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function ArticleCard({ article }: { article: Article }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{article.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p>{article.summary}</p>
        <Button onClick={() => handleBookmark(article.id)}>
          加入書籤
        </Button>
      </CardContent>
    </Card>
  )
}
```

### 5.2 設計系統建立

**設計 Token 系統**：
```typescript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // 品牌色
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          900: '#1e3a8a',
        },
        // 語義色
        success: '#10b981',
        warning: '#f59e0b',
        error: '#ef4444',
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans TC', 'sans-serif'],
      },
    },
  },
}
```

**設計文檔（Storybook）**：
```bash
# 安裝 Storybook
npx storybook@latest init
```

**組件文檔示例**：
```typescript
// stories/Button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './Button'

const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'secondary', 'outline'],
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
    },
  },
}

export default meta
type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: {
    variant: 'primary',
    children: '主要按鈕',
  },
}

export const Secondary: Story = {
  args: {
    variant: 'secondary',
    children: '次要按鈕',
  },
}
```

### 5.3 自動化測試策略

**測試金字塔**：
```
        ╱╲
       ╱  ╲      E2E 測試（10%）
      ╱ E2E╲     Playwright / Cypress
     ╱──────╲
    ╱        ╲   整合測試（20%）
   ╱ 整合測試 ╲  React Testing Library
  ╱────────────╲
 ╱              ╲ 單元測試（70%）
╱   單元測試     ╲ Jest / Vitest
╱────────────────╲
```

**單元測試示例**：
```typescript
// __tests__/utils/formatDate.test.ts
import { formatRelativeTime } from '@/lib/utils'

describe('formatRelativeTime', () => {
  it('應該顯示「剛剛」對於1分鐘內的時間', () => {
    const now = new Date()
    expect(formatRelativeTime(now)).toBe('剛剛')
  })

  it('應該顯示「X分鐘前」對於1小時內的時間', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000)
    expect(formatRelativeTime(fiveMinutesAgo)).toBe('5分鐘前')
  })

  it('應該顯示「X小時前」對於24小時內的時間', () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000)
    expect(formatRelativeTime(twoHoursAgo)).toBe('2小時前')
  })
})
```

**整合測試示例**：
```typescript
// __tests__/components/ArticleCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { ArticleCard } from '@/components/ArticleCard'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function renderWithProviders(ui: React.ReactNode) {
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

describe('ArticleCard', () => {
  const mockArticle = {
    id: 1,
    title: '測試新聞標題',
    summary: '這是新聞摘要',
    source: '測試來源',
    publishedAt: new Date().toISOString(),
  }

  it('應該正確渲染文章標題', () => {
    renderWithProviders(<ArticleCard article={mockArticle} />)
    expect(screen.getByText('測試新聞標題')).toBeInTheDocument()
  })

  it('點擊書籤按鈕應該調用 onBookmark', () => {
    const onBookmark = jest.fn()
    renderWithProviders(
      <ArticleCard article={mockArticle} onBookmark={onBookmark} />
    )
    
    fireEvent.click(screen.getByLabelText('加入書籤'))
    expect(onBookmark).toHaveBeenCalledWith(mockArticle.id)
  })
})
```

**E2E 測試示例（Playwright）**：
```typescript
// e2e/article-flow.spec.ts
import { test, expect } from '@playwright/test'

test.describe('文章瀏覽流程', () => {
  test('應該能夠瀏覽文章列表並查看詳情', async ({ page }) => {
    // 訪問首頁
    await page.goto('/')
    
    // 等待文章列表加載
    await page.waitForSelector('[data-testid="article-card"]')
    
    // 點擊第一篇文章
    const firstArticle = page.locator('[data-testid="article-card"]').first()
    await firstArticle.click()
    
    // 驗證進入詳情頁
    await expect(page).toHaveURL(/\/articles\/\d+/)
    
    // 驗證標題顯示
    const title = page.locator('h1')
    await expect(title).toBeVisible()
  })

  test('應該能夠添加書籤', async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector('[data-testid="article-card"]')
    
    // 點擊書籤按鈕
    const bookmarkButton = page.locator('[data-testid="bookmark-button"]').first()
    await bookmarkButton.click()
    
    // 驗證書籤狀態變化
    await expect(bookmarkButton).toHaveAttribute('data-bookmarked', 'true')
  })
})
```

**測試覆蓋率配置**：
```json
// jest.config.json
{
  "collectCoverageFrom": [
    "components/**/*.{ts,tsx}",
    "lib/**/*.{ts,tsx}",
    "!**/*.stories.tsx",
    "!**/*.d.ts"
  ],
  "coverageThreshold": {
    "global": {
      "branches": 70,
      "functions": 70,
      "lines": 80,
      "statements": 80
    }
  }
}
```

---

## 6. 總結與建議

### 6.1 核心建議

1. **技術棧統一**：
   - Web: Next.js 14 + React + TypeScript
   - Mobile: React Native (Expo) 或 原生 SwiftUI + Jetpack Compose
   - 共享: TypeScript 類型定義、業務邏輯、API 客戶端

2. **性能優先**：
   - 實施分層緩存策略
   - 圖片自動優化（WebP、懶加載）
   - PWA 支持離線訪問

3. **設計系統**：
   - 建立統一嘅設計 Token
   - 使用 shadcn/ui 構建組件庫
   - Storybook 文檔化組件

4. **測試覆蓋**：
   - 單元測試覆蓋核心邏輯（>80%）
   - 整合測試覆蓋關鍵用戶流程
   - E2E 測試覆蓋核心業務場景

### 6.2 風險與應對

| 風險 | 影響 | 應對策略 |
|------|------|---------|
| 跨端一致性 | 中 | 建立設計系統，統一組件庫 |
| 性能下降 | 高 | 定期性能審計，監控核心指標 |
| 技術債累積 | 中 | 代碼審查，重構計劃 |
| 團隊技能不足 | 中 | 培訓計劃，技術分享 |

### 6.3 下一步行動

**短期（1個月）**：
- [ ] 搭建 Next.js 14 項目基礎架構
- [ ] 配置 Tailwind CSS + shadcn/ui
- [ ] 實現核心頁面（首頁、文章列表、詳情頁）
- [ ] 整合 React Query + API 客戶端

**中期（3個月）**：
- [ ] 完成 PWA 配置，實現離線訪問
- [ ] 建立組件庫文檔（Storybook）
- [ ] 實施自動化測試（>70% 覆蓋率）
- [ ] 性能優化（LCP < 2.5s）

**長期（6個月）**：
- [ ] 評估 React Native 移動端開發
- [ ] 建立完整嘅設計系統
- [ ] 實施 CI/CD 自動化部署
- [ ] 監控同分析系統整合

---

**文檔版本**：v1.0  
**最後更新**：2026-07-26  
**審查人**：資深前端開發工程師
