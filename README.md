# wikiflash

Convert a markdown file of Wikipedia/Wikiwand links into an Anki flashcard deck.

### How to run

```sh
uv run main.py <input.md> [output.apkg] [--deck-name "My Deck"]
uv run main.py <input.md> --limit 10 # defaults to wikiflash.apkg
```

### Requirements

Set an `ANTHROPIC_API_KEY` environment variable either through an .env file or in the command line.
