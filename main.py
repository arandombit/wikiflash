#!/usr/bin/env python3
import re
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

load_dotenv()
import genanki

WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_EXTRACT_API = "https://en.wikipedia.org/w/api.php"
REQUEST_DELAY = 0.5   # seconds between Wikipedia requests (be polite)
MAX_EXTRACT_CHARS = 6000  # trim long articles before sending to Claude

ANKI_MODEL = genanki.Model(
  1607392319,
  "WikiFlash Q&A",
  fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Source"}],
  templates=[{
    "name": "Card",
    "qfmt": "{{Front}}",
    "afmt": "{{FrontSide}}<hr id='answer'>{{Back}}<br><small>{{Source}}</small>",
  }],
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
