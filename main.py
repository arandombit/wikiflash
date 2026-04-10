#!/usr/bin/env python3
import re
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

load_dotenv()
import genanki
import requests

WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_EXTRACT_API = "https://en.wikipedia.org/w/api.php"
REQUEST_DELAY = 0.5  # seconds between Wikipedia requests
MAX_EXTRACT_CHARS = 12000  # trim long articles before sending to Claude

ANKI_MODEL = genanki.Model(
  1607392319,
  "WikiFlash Q&A",
  fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Source"}],
  templates=[{
    "name": "Card",
    "qfmt": "{{Front}}",
    "afmt": "{{FrontSide}}<hr id='answer'>{{Back}}<br><small>{{Source}}</small>",
  }],
  css=".card { text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 50vh; }",
)

# ── URL helpers ───────────────────────────────────────────────────────────────

def extract_article_title(url: str) -> str | None:
  """Return the Wikipedia article title from a Wikipedia or Wikiwand URL."""
  parsed = urlparse(url)
  host = parsed.netloc.lower()
  path = parsed.path

  if "wikipedia.org" in host or "wikiwand.com" in host:
    # Skip category / special pages
    if re.search(r"/(Category|Special|Wikipedia|Help|Talk|File|Template):", path, re.I):
      return None
    # /wiki/Article_Title  or  /en/Article_Title
    match = re.match(r"^/(?:wiki/|[a-z]{2,3}/)(.+)$", path)
    if match:
      return unquote(match.group(1)).replace("_", " ")
  return None


def parse_urls(filepath: str) -> list[tuple[str, str]]:
  """Parse the markdown file and return (url, article_title) pairs."""
  results = []
  seen = set()
  with open(filepath, encoding="utf-8") as f:
    for line in f:
      url = line.strip()
      if not url or not url.startswith("http"):
        continue
      title = extract_article_title(url)
      if title and title not in seen:
        seen.add(title)
        results.append((url, title))
  return results

# ── Wikipedia fetch ───────────────────────────────────────────────────────────

def fetch_wikipedia_extract(title: str) -> str | None:
  """Fetch a plain-text extract for an article using the MediaWiki API."""
  params = {
    "action": "query",
    "titles": title,
    "prop": "extracts",
    "exintro": False,
    "explaintext": True,
    "exsectionformat": "plain",
    "format": "json",
    "redirects": 1,
  }
  try:
    resp = requests.get(WIKI_EXTRACT_API, params=params, timeout=10, headers={"User-Agent": "WikiFlash/1.0 (anki-card-generator)"})
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    for page in pages.values():
      if "missing" in page:
        return None
      extract = page.get("extract", "").strip()
      return extract[:MAX_EXTRACT_CHARS] if extract else None
  except Exception as e:
    print(f"  [warn] Wikipedia fetch failed for '{title}': {e}")
    return None
