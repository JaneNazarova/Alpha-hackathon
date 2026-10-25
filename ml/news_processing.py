# Очищает новости и извлекает их признаки.
import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser

from ml.config import GEOGRAPHY, MECHANISMS, SCHEMA_VERSION, SECTORS, TOPICS


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_text(value):
    parser = _Text()
    parser.feed(str(value or ""))
    return re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()


def normalize(value):
    return " ".join(re.findall(r"[\w]+", str(value).casefold().replace("ё", "е")))


def mentions(text, term):
    return bool(re.search(r"(?<!\w)" + re.escape(term.casefold()).replace(r"\ ", r"\s+") , text.casefold()))


def parse_datetime(value):
    if isinstance(value, datetime):
        date = value
    elif value:
        try:
            date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            try:
                date = parsedate_to_datetime(str(value))
            except (ValueError, TypeError, OverflowError):
                return None
    else:
        return None
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)


def process_news(article):
    if not isinstance(article, dict):
        raise ValueError("article must be a mapping")
    title = clean_text(article.get("title"))
    content = clean_text(article.get("content") or article.get("summary"))
    if not title or not (article.get("id") or article.get("article_id")):
        raise ValueError("News needs a nonempty id and title")
    text = f"{title}. {content}"
    lower = text.casefold()
    categories = [key for key, terms in TOPICS.items() if any(mentions(lower, t) for t in terms)]
    sector_tags = [key for key, spec in SECTORS.items() if any(mentions(lower, t) for t in spec["terms"])]
    geo = [key for key, terms in GEOGRAPHY.items() if any(mentions(lower, t) for t in terms)]
    participants = sorted(set(re.findall(r"\b(?:SYNTHETIC_U_[\w-]+|U_\d+)\b", text)))
    participants += sorted(set(re.findall(r'(?:ООО|ПАО|АО)\s+[«"]([^»"]+)[»"]', text)))
    participants += [name for name, terms in {"Банк России": ("банк россии", "цб"),
                     "Альфа-Банк": ("альфа-банк",), "ФНС": ("фнс",)}.items()
                     if any(mentions(lower, t) for t in terms)]
    dates = re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})\b", text)
    indicators = [{"text": m.group(0), "value": m.group(1).replace(",", "."),
                   "unit": m.group(2), "source_id": str(article.get("id") or article["article_id"])}
                  for m in re.finditer(r"(?<![\w.-])(\d+(?:[.,]\d+)?)\s*(%|млрд|млн|тыс|рублей|руб\b|б\.п\.)", text)]
    article_id = str(article.get("id") or article["article_id"])
    sentences = [s.strip() for s in re.split(r"(?<=[!?])\s+|(?<!\d)\.\s+", text) if s.strip()]
    facts = [{"text": s[:1000], "source_id": article_id, "status": "reported_by_source"} for s in sentences[:5]]
    published = parse_datetime(article.get("published_at"))
    url = str(article.get("source_url") or article.get("url") or "")
    result = {**article, "schema_version": SCHEMA_VERSION, "id": article_id, "article_id": article_id,
              "title": title, "content": content, "summary": clean_text(article.get("summary")) or content[:400],
              "source_url": url, "source_name": str(article.get("source_name") or "Unknown"),
              "published_at": published.isoformat() if published else None,
              "category": categories[0] if categories else "other", "categories": categories,
              "facts": facts, "participants": list(dict.fromkeys(participants)),
              "industry_tags": sector_tags, "geographies": geo,
              "mechanisms": [MECHANISMS[c] for c in categories], "indicators": indicators,
              "temporal_context": {"mentioned_dates": dates,
                  "forecast_language": any(mentions(lower, t) for t in ("прогноз", "ожида", "может", "планиру"))},
              "processing_status": "processed", "normalized_title": normalize(title),
              "content_hash": hashlib.sha256(normalize(text).encode()).hexdigest(),
              "uncertainties": []}
    if not published:
        result["uncertainties"].append("Publication date missing or invalid; no freshness bonus.")
    if not url:
        result["uncertainties"].append("Source URL not supplied; source cannot be opened.")
    if not categories:
        result["uncertainties"].append("No topic matched the limited MVP vocabulary.")
    return result
