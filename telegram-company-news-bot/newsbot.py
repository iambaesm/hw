#!/usr/bin/env python3
"""Daily multi-company news digest for Telegram using Naver News Search API."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
TELEGRAM_MESSAGE_LIMIT = 3900
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "companies.json"


@dataclass(frozen=True)
class Article:
    title: str
    description: str
    link: str
    published_at: datetime
    score: int = 0


def clean_text(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()


def normalize_title(value: str) -> str:
    value = clean_text(value).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", value)


def canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"}:
        return ""
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host, path, "", ""))


def shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    companies = config.get("companies")
    if not isinstance(companies, list) or not companies:
        raise ValueError("config/companies.json에 companies를 1개 이상 등록해야 합니다.")

    for company in companies:
        if not company.get("name") or not company.get("queries"):
            raise ValueError("각 회사에는 name과 queries가 필요합니다.")
    return config


def fetch_naver_news(
    query: str,
    client_id: str,
    client_secret: str,
    display: int = 100,
) -> list[dict[str, Any]]:
    query_string = urlencode({"query": query, "display": display, "sort": "date"})
    request = Request(
        f"{NAVER_NEWS_URL}?{query_string}",
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("items", [])


def is_relevant(text: str, company: dict[str, Any]) -> bool:
    lowered = text.lower()
    include_any = company.get("include_any", [])
    exclude_any = company.get("exclude_any", [])

    if include_any and not any(str(word).lower() in lowered for word in include_any):
        return False
    if exclude_any and any(str(word).lower() in lowered for word in exclude_any):
        return False
    return True


def article_score(title: str, description: str, company: dict[str, Any]) -> int:
    title_lower = title.lower()
    full_text = f"{title} {description}".lower()
    score = 0

    for word in company.get("include_any", []):
        needle = str(word).lower()
        if needle in title_lower:
            score += 3
        elif needle in full_text:
            score += 1

    for word in company.get("priority_keywords", []):
        needle = str(word).lower()
        if needle in title_lower:
            score += 4
        elif needle in full_text:
            score += 2

    return score


def parse_article(item: dict[str, Any], company: dict[str, Any]) -> Article | None:
    try:
        published_at = parsedate_to_datetime(item["pubDate"])
    except (KeyError, TypeError, ValueError):
        return None

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    title = clean_text(str(item.get("title", "")))
    description = clean_text(str(item.get("description", "")))
    link = canonical_url(str(item.get("originallink") or item.get("link") or ""))
    if not title or not link or not is_relevant(f"{title} {description}", company):
        return None

    return Article(
        title=title,
        description=description,
        link=link,
        published_at=published_at.astimezone(timezone.utc),
        score=article_score(title, description, company),
    )


def deduplicate(articles: list[Article]) -> list[Article]:
    unique: list[Article] = []
    seen_urls: set[str] = set()

    for article in sorted(
        articles,
        key=lambda item: (item.score, item.published_at),
        reverse=True,
    ):
        if article.link in seen_urls:
            continue

        normalized = normalize_title(article.title)
        is_duplicate = any(
            SequenceMatcher(None, normalized, normalize_title(saved.title)).ratio() >= 0.88
            for saved in unique
        )
        if is_duplicate:
            continue

        unique.append(article)
        seen_urls.add(article.link)

    return unique


def collect_company_news(
    company: dict[str, Any],
    cutoff: datetime,
    client_id: str,
    client_secret: str,
) -> list[Article]:
    collected: list[Article] = []
    for query in company["queries"]:
        for item in fetch_naver_news(str(query), client_id, client_secret):
            article = parse_article(item, company)
            if article and article.published_at >= cutoff:
                collected.append(article)
    return deduplicate(collected)


def importance_icon(score: int) -> str:
    if score >= 8:
        return "🔴"
    if score >= 4:
        return "🟠"
    return "⚪"


def format_article(article: Article, index: int, local_tz: Any) -> str:
    title = html.escape(article.title)
    summary = html.escape(shorten(article.description or "기사 요약문 없음", 220))
    link = html.escape(article.link, quote=True)
    published = article.published_at.astimezone(local_tz).strftime("%m/%d %H:%M")
    return (
        f"{importance_icon(article.score)} <b>{index}. {title}</b>\n"
        f"{summary}\n"
        f"<a href=\"{link}\">기사 보기</a> · {published}"
    )


def build_digest(
    config: dict[str, Any],
    company_articles: list[tuple[dict[str, Any], list[Article]]],
    now_local: datetime,
) -> str:
    title = html.escape(str(config.get("digest_title", "기업 뉴스 Daily Monitor")))
    lines = [f"📰 <b>{title}</b> — {now_local:%Y.%m.%d}"]
    max_per_company = int(config.get("max_articles_per_company", 8))

    for company, articles in company_articles:
        lines.append(f"\n<b>■ {html.escape(str(company['name']))}</b>")
        if not articles:
            lines.append("지난 조회기간의 관련 기사가 없습니다.")
            continue

        for index, article in enumerate(articles[:max_per_company], 1):
            lines.append(format_article(article, index, now_local.tzinfo))

    lines.append("\n※ 네이버 뉴스 검색 결과를 중복 제거·키워드 우선순위로 정리함.")
    return "\n\n".join(lines)


def split_telegram_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(block) > limit:
            chunks.append(block[:limit])
            block = block[limit:]
        current = block
    if current:
        chunks.append(current)
    return chunks


def send_telegram(token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in split_telegram_message(message):
        payload = json.dumps(
            {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=20):
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram 기업 뉴스 데일리 봇")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--hours", type=int, default=None, help="조회시간을 임시로 덮어씀")
    parser.add_argument("--dry-run", action="store_true", help="Telegram 발송 없이 화면 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        client_id = os.environ["NAVER_CLIENT_ID"]
        client_secret = os.environ["NAVER_CLIENT_SECRET"]
        lookback_hours = args.hours or int(config.get("lookback_hours", 26))

        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc - timedelta(hours=lookback_hours)

        try:
            from zoneinfo import ZoneInfo

            local_tz = ZoneInfo(str(config.get("timezone", "Asia/Seoul")))
        except Exception:
            local_tz = timezone(timedelta(hours=9))

        company_articles = [
            (
                company,
                collect_company_news(company, cutoff, client_id, client_secret),
            )
            for company in config["companies"]
        ]
        message = build_digest(config, company_articles, now_utc.astimezone(local_tz))

        if args.dry_run:
            print(message)
            return 0

        token = os.environ["TELEGRAM_TOKEN"]
        chat_id = os.environ["TELEGRAM_CHAT_ID"]
        send_telegram(token, chat_id, message)
        return 0
    except KeyError as exc:
        print(f"필수 환경변수가 없습니다: {exc.args[0]}", file=sys.stderr)
    except (OSError, ValueError, URLError) as exc:
        print(f"실행 실패: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
