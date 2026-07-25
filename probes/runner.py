"""
探針執行器
"""
import asyncio
from datetime import datetime
from typing import Optional
from .registry import ProbeRegistry, auto_discover_probes
from .models import ProbeResult


class ProbeRunner:
    """探針執行器"""
    
    def __init__(self):
        auto_discover_probes()
    
    async def run_probe(self, source_name: str) -> ProbeResult:
        """執行單個探針"""
        try:
            probe_class = ProbeRegistry.get(source_name)
            async with probe_class() as probe:
                articles = await probe.fetch()
                return ProbeResult(
                    source=source_name,
                    articles=articles
                )
        except Exception as e:
            return ProbeResult(
                source=source_name,
                articles=[],
                error=str(e)
            )
    
    async def run_all(self) -> list[ProbeResult]:
        """並行執行所有探針"""
        sources = ProbeRegistry.list_sources()
        tasks = [self.run_probe(source) for source in sources]
        return await asyncio.gather(*tasks)
    
    def list_sources(self) -> list[str]:
        """列出所有可用新聞源"""
        return ProbeRegistry.list_sources()


async def main():
    """測試入口"""
    runner = ProbeRunner()
    
    print("可用新聞源：")
    for source in runner.list_sources():
        print(f"  - {source}")
    
    print("\n開始採集...")
    results = await runner.run_all()
    
    for result in results:
        if result.ok:
            print(f"\n✓ {result.source}: 獲取 {len(result.articles)} 篇文章")
            for article in result.articles[:3]:  # 只顯示前3篇
                print(f"  - {article.title}")
                print(f"    {article.url}")
        else:
            print(f"\n✗ {result.source}: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
