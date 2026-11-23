import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict

from collector.config import FEEDS
from collector.fetcher import RSSFetcher
from collector.processor import InterviewInsightEngine
from collector.sample_data import SAMPLE_INTERVIEW_SEED
from backend.database import parse_article_datetime

def run_pipeline(output_paths: List[str] = None):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if output_paths is None:
        output_paths = [
            os.path.join(base_dir, "data", "jobs_and_trends.json"),
            os.path.join(base_dir, "data", "news.json"),
            os.path.join(base_dir, "frontend", "jobs_and_trends.json"),
            os.path.join(base_dir, "frontend", "news.json"),
            os.path.join(base_dir, "jobs_and_trends.json"),
            os.path.join(base_dir, "news.json")
        ]

    fetcher = RSSFetcher(timeout=5)
    insight_engine = InterviewInsightEngine()

    logging.info(f"🎯 Starting TechPrep-AI Pipeline with {len(FEEDS)} feed endpoints...")
    collected_raw_items = []

    # 1. RSS 실시간 수집 시도
    for feed in FEEDS:
        items = fetcher.fetch_feed(feed)
        collected_raw_items.extend(items)

    logging.info(f"Collected {len(collected_raw_items)} articles from live RSS feeds.")

    # 2. 오프라인 또는 네트워크 제약 시 실무 면접 대비 시드 데이터셋 결합
    if not collected_raw_items:
        logging.info("Network feeds unreachable or empty. Loading curated developer interview & trends dataset...")
        collected_raw_items = SAMPLE_INTERVIEW_SEED

    # 3. 데이터 중복 제거 (링크 및 제목 기준)
    seen_keys = set()
    unique_items = []
    for item in collected_raw_items:
        key = item.get("link") or item.get("title")
        if key not in seen_keys:
            seen_keys.add(key)
            unique_items.append(item)

    # 4. AI 에이전트 가공: 요약, 카테고리 분류, 면접 예상 질문 & 핵심 인사이트 도출
    processed_articles = []
    category_counts = {}

    for raw in unique_items:
        processed = insight_engine.process(raw)
        if processed is not None:
            processed_articles.append(processed)
            cat = processed["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

    # 5. 기존 아카이빙 데이터가 있을 경우 필터링을 거쳐 누적(Append / Merge) 처리
    # (단, 30일 경과 기사는 누적 시점에도 제외하여 오래된 기사 자동 소멸)
    retention_days = int(os.environ.get("ARTICLE_RETENTION_DAYS", "30").strip())
    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=retention_days)

    archive_path = os.path.join(base_dir, "data", "jobs_and_trends.json")
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                old_articles = old_data.get("articles", [])
                existing_links = {a.get("link") for a in processed_articles}
                for old_art in old_articles:
                    # 30일 초과 오래된 기사는 필터링 제외
                    p_str = old_art.get("published") or old_art.get("created_at") or old_art.get("published_at")
                    art_dt = parse_article_datetime(p_str)
                    if art_dt is not None and art_dt < cutoff_dt:
                        continue

                    # 기존 기사도 IT 관련성 검증
                    title = old_art.get("title", "")
                    desc = old_art.get("summary", "") or old_art.get("raw_snippet", "")
                    if insight_engine.is_relevant_it_article(title, desc):
                        if old_art.get("link") not in existing_links:
                            processed_articles.append(old_art)
                            existing_links.add(old_art.get("link"))
                            c = old_art.get("category", "기타")
                            category_counts[c] = category_counts.get(c, 0) + 1
        except Exception as e:
            logging.warning(f"Failed to read existing archive for append: {e}")

    # 6. LLM(Gemini) 기반 기사별 고유한 실무 핵심 인사이트 생성 (배치 처리)
    logging.info(f"✨ Enhancing {len(processed_articles)} articles with unique LLM insights...")
    insight_engine.enrich_insights_with_llm(processed_articles)

    # 7. 최종 메타데이터 및 출력 생성
    payload = {
        "metadata": {
            "title": "TechPrep-AI: 개발자 취업 및 면접 대비 실시간 IT 트렌드 브리핑",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_articles": len(processed_articles),
            "categories": category_counts
        },
        "articles": processed_articles
    }

    # 8. 대상 파일들에 JSON 동기화 저장
    for path in output_paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logging.info(f"✅ TechPrep-AI dataset saved to: {path}")

    print("\n=== TechPrep-AI Pipeline Summary ===")
    print(f"Total Interview Ready Articles: {len(processed_articles)}")
    print(f"Category Breakdown: {category_counts}")
    print("=====================================\n")

if __name__ == "__main__":
    run_pipeline()
