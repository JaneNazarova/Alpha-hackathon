import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import NewsArticle


def clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def parse_date(value):
    if not value:
        return None
    try:
        date = parsedate_to_datetime(value)
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    except (TypeError, ValueError):
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
        except ValueError:
            return None


async def fetch_rss(db: Session) -> dict:
    settings = get_settings()
    inserted, skipped, failures = 0, 0, []
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True,
                                 headers={"User-Agent": "AlphaHackNewsAnalytics/1.0 (RSS reader)"}) as client:
        for feed_url in settings.feeds:
            try:
                response = await client.get(feed_url)
                response.raise_for_status()
                root = ET.fromstring(response.content)
                entries = root.findall(".//item")
                if not entries:
                    entries = root.findall(".//{*}entry")
                for entry in entries[:settings.max_feed_items]:
                    values = {}
                    for child in entry:
                        key = child.tag.split("}")[-1].lower()
                        if key == "link" and child.attrib.get("href"):
                            values[key] = child.attrib["href"]
                        elif child.text:
                            values[key] = child.text.strip()
                    title = clean_html(values.get("title", ""))
                    url = values.get("link", "").strip()
                    content = clean_html(values.get("description") or values.get("encoded") or values.get("summary") or "")
                    if not title or not url:
                        skipped += 1
                        continue
                    content_hash = hashlib.sha256((title + " " + content).encode("utf-8")).hexdigest()
                    exists = db.scalar(select(NewsArticle.id).where((NewsArticle.url == url) | (NewsArticle.content_hash == content_hash)))
                    if exists:
                        skipped += 1
                        continue
                    article = NewsArticle(id=str(uuid4()), title=title, content=content,
                        summary=content[:400], source_name="Банк России" if "cbr.ru" in feed_url else feed_url,
                        url=url, published_at=parse_date(values.get("pubdate") or values.get("published") or values.get("updated")),
                        content_hash=content_hash, processing_status="processed")
                    article.category, article.facts = classify(article.title + " " + content)
                    db.add(article)
                    inserted += 1
            except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
                failures.append({"source": feed_url, "error": type(exc).__name__})
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "failures": failures}


def classify(text: str):
    text = text.lower()
    groups = {
        "monetary_policy": ["ключев", "ставк", "цб", "инфляц", "денежно-кредит"],
        "macroeconomics": ["ввп", "экономик", "промышленност", "рост цен"],
        "currency": ["рубл", "валют", "доллар", "юан", "курс"],
        "commodities": ["нефт", "газ", "золот", "зерн", "сырь"],
        "tax_regulation": ["налог", "закон", "регулирован", "пошлин"],
        "logistics_trade": ["экспорт", "импорт", "логист", "постав"],
        "labor": ["занятост", "зарплат", "рынок труда", "безработиц"],
    }
    found = [category for category, words in groups.items() if any(word in text for word in words)]
    return (found[0] if found else "corporate_events"), found
