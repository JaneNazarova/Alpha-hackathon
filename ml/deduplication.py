# Объединяет дубли новостей и сохраняет дополнительные источники.
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ml.news_processing import normalize, parse_datetime, process_news


def canonical_url(url):
    if not url:
        return None
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_") and k not in {"gclid", "fbclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), ""))


def _same_event(a, b, threshold):
    au, bu = canonical_url(a.get("source_url")), canonical_url(b.get("source_url"))
    if au and au == bu:
        return True
    if a["content_hash"] == b["content_hash"]:
        return True
    at, bt = normalize(a["title"]), normalize(b["title"])
    av = {(v["value"], v["unit"]) for v in a["indicators"]}
    bv = {(v["value"], v["unit"]) for v in b["indicators"]}
    if av and bv and av != bv:
        return False
    if re.findall(r"\d+(?:[.,]\d+)?", a["title"]) != re.findall(r"\d+(?:[.,]\d+)?", b["title"]):
        return False
    for words in (("повыс", "увелич", "вырос", "рост"), ("сниз", "сократ", "упал", "паден"), ("сохран", "не измен")):
        if any(w in at for w in words) != any(w in bt for w in words):
            return False
    ad, bd = parse_datetime(a.get("published_at")), parse_datetime(b.get("published_at"))
    if not ad or not bd or abs((ad - bd).total_seconds()) > 48 * 3600:
        return False
    aset, bset = set(at.split()), set(bt.split())
    similarity = len(aset & bset) / len(aset | bset) if aset | bset else 0
    return len(aset & bset) >= 4 and similarity >= threshold


def group_news(articles, threshold=.8):
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0,1]")
    groups = []
    for raw in articles:
        item = process_news(raw)
        group = next((g for g in groups if _same_event(g[0], item, threshold)), None)
        if group is None:
            groups.append([item])
        else:
            group.append(item)
    results = []
    for members in groups:
        representative = max(members, key=lambda a: (len(a["content"]), bool(a.get("source_url"))))
        result = dict(representative)
        result["duplicate_article_ids"] = [a["id"] for a in members if a is not representative]
        result["additional_sources"] = [{"id": a["id"], "url": a.get("source_url"), "title": a["title"],
                                           "source_name": a.get("source_name")} for a in members if a is not representative]
        result["event_id"] = min(a["id"] for a in members)
        results.append(result)
    return results
