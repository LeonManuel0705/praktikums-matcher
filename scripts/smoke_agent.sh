#!/usr/bin/env bash
CB="${CLAUDE_CODE_EXECPATH:?}"
"$CB" -p "Suche mit WebSearch nach genau EINEM aktuell ausgeschriebenen Praktikum bei einem Tech-Startup in Berlin. Antworte AUSSCHLIESSLICH mit einem JSON-Objekt der Form {\"title\":\"\",\"company\":\"\",\"city\":\"\",\"url\":\"\"} und ohne Markdown-Fence." \
  --output-format json \
  --allowedTools WebSearch WebFetch \
  --max-turns 12 \
  --model claude-haiku-4-5-20251001
