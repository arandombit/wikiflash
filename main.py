#!/usr/bin/env python3
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
