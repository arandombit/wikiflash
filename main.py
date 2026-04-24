#!/usr/bin/env python3
import argparse
import json
import re
import time
from urllib.parse import unquote, urlparse

import anthropic
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
    # /wiki/Article_Title or /en/Article_Title
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

# ── Claude Q&A generation ─────────────────────────────────────────────────────

_claude = anthropic.Anthropic()

SYSTEM_PROMPT = """\
You are a precise flashcard author. Given a Wikipedia article extract, produce
3–7 question-and-answer pairs that capture the most important facts.

Rules:
- Questions must be specific and unambiguous.
- Answers should be concise (1–3 sentences).
- Do NOT repeat the article title verbatim as the entire answer.
- Output ONLY valid JSON: a list of objects with "q" and "a" keys.
  Example: [{"q": "...", "a": "..."}, ...]
- No markdown fences, no commentary outside the JSON array."""


def generate_qa_pairs(title: str, extract: str) -> list[dict]:
  user_msg = f"Article title: {title}\n\n{extract}"
  try:
    response = _claude.messages.create(
      model="claude-opus-4-5",
      max_tokens=1024,
      system=SYSTEM_PROMPT,
      messages=[{"role": "user", "content": user_msg}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown fences if Claude wraps the JSON anyway
    if raw.startswith("```"):
      raw = re.sub(r"^```[a-z]*\n?", "", raw)
      raw = re.sub(r"\n?```$", "", raw)
    pairs = json.loads(raw)
    if isinstance(pairs, list):
      return [p for p in pairs if isinstance(p, dict) and "q" in p and "a" in p]
    return []
  except Exception as e:
    print(f"  [warn] Claude generation failed for '{title}': {e}")
    return []

# ── Anki helpers ──────────────────────────────────────────────────────────────

def make_note(question: str, answer: str, source_url: str) -> genanki.Note:
  return genanki.Note(model=ANKI_MODEL, fields=[question, answer, f'<a href="{source_url}">{source_url}</a>'])

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a markdown file of Wikipedia links into an Anki deck."
    )
    parser.add_argument("input", help="Markdown file containing one URL per line")
    parser.add_argument(
        "output",
        nargs="?",
        default="wikiflash.apkg",
        help="Output .apkg file (default: wikiflash.apkg)",
    )
    parser.add_argument(
        "--deck-name", default="WikiFlash", help="Anki deck name (default: WikiFlash)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only process the first N articles",
    )
    args = parser.parse_args()

    articles = parse_urls(args.input)
    if args.limit is not None:
        articles = articles[: args.limit]
    if not articles:
        print("No valid Wikipedia/Wikiwand URLs found in the input file.")
        return

    print(f"Found {len(articles)} article(s). Generating flashcards…")

    deck = genanki.Deck(2059400110, args.deck_name)
    total_cards = 0

    for i, (url, title) in enumerate(articles, 1):
        print(f"[{i}/{len(articles)}] {title}")

        extract = fetch_wikipedia_extract(title)
        if not extract:
            print(f"  [skip] No extract available.")
            time.sleep(REQUEST_DELAY)
            continue

        pairs = generate_qa_pairs(title, extract)
        if not pairs:
            print(f"  [skip] No Q&A pairs generated.")
            time.sleep(REQUEST_DELAY)
            continue

        for pair in pairs:
            deck.add_note(make_note(pair["q"], pair["a"], url))

        total_cards += len(pairs)
        print(f"  +{len(pairs)} card(s)  (total: {total_cards})")
        time.sleep(REQUEST_DELAY)

    genanki.Package(deck).write_to_file(args.output)
    print(f"\nDone! {total_cards} card(s) written to '{args.output}'.")
