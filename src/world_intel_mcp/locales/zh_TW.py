"""zh-TW (Taiwan Traditional Chinese) message catalog.

Keys are the exact English source strings. Terminology follows GLOSSARY.md.
Sections are merged into MESSAGES; a key may live in only one section.
"""

# Click's own help chrome ("Usage:", "Options:" ...) -- see cli.py.
CLICK: dict[str, str] = {}

# `intel` CLI: command help, table headers, console messages.
CLI: dict[str, str] = {}

# reports.py, daily digest, situation brief.
REPORTS: dict[str, str] = {}

# dashboard/index.html: static text, attributes and JS-built strings.
DASHBOARD: dict[str, str] = {}

MESSAGES: dict[str, str] = {**CLICK, **CLI, **REPORTS, **DASHBOARD}
