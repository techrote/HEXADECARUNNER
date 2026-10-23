"""Validate local Markdown documentation links, GitHub anchors and retrieval routing.

No dependencies or network required. External URLs are deliberately excluded.
Run: python -m unittest discover -s tests -v
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "AGENTS.md",
    "docs/INDEX.md",
    "docs/AGENT_PLAYBOOK.md",
    "docs/REUSE.md",
    "docs/ARCHITECTURE.md",
    "docs/OPERATIONS.md",
    "docs/QUALIFICATION.md",
)

HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
FENCE = re.compile(r"^\s{0,3}(" + r"`{3,}|~{3,}" + r")")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^)\"]*['\"])?\)")
LABEL_LINK = re.compile(r"!?\[([^\]]+)\]\([^)]+\)")


def non_fenced_lines(text: str):
    """Ignore links/headings that are examples inside Markdown fenced code."""
    marker = ""
    width = 0
    for number, line in enumerate(text.splitlines(), 1):
        candidate = FENCE.match(line)
        if candidate:
            run = candidate.group(1)
            if not marker:
                marker, width = run[0], len(run)
                continue
            if run[0] == marker and len(run) >= width:
                marker, width = "", 0
                continue
        if not marker:
            yield number, line


def github_slug(heading: str) -> str:
    """Subset of GitHub's heading slug rules used by this ASCII Markdown corpus."""
    heading = LABEL_LINK.sub(lambda match: match.group(1), heading)
    heading = re.sub(r"</?[^>]*>", "", heading)
    heading = heading.replace("`", "").strip().lower()
    heading = re.sub(r"[^\w\- ]", "", heading)
    return heading.replace(" ", "-")


def heading_anchors(text: str) -> set[str]:
    seen = defaultdict(int)
    anchors = set()
    for _, line in non_fenced_lines(text):
        match = HEADING.match(line)
        if not match:
            continue
        slug = github_slug(match.group(1))
        if not slug:
            continue
        suffix = seen[slug]
        seen[slug] += 1
        anchors.add(slug if not suffix else f"{slug}-{suffix}")
    return anchors


class DocumentationNavigationTest(unittest.TestCase):
    def test_required_entrypoints_exist_and_link_to_index(self):
        for relative in REQUIRED:
            with self.subTest(document=relative):
                path = ROOT / relative
                self.assertTrue(path.is_file(), f"missing {relative}")
                body = path.read_text(encoding="utf-8")
                self.assertTrue(body.startswith("# "), f"missing H1: {relative}")
                if relative.startswith("docs/") and relative != "docs/INDEX.md":
                    self.assertIn("INDEX.md", "\n".join(body.splitlines()[:6]),
                                  f"top navigation does not route to INDEX: {relative}")
        index = (ROOT / "docs/INDEX.md").read_text(encoding="utf-8")
        for relative in REQUIRED:
            if relative == "docs/INDEX.md":
                continue
            name = Path(relative).name
            with self.subTest(index_links_to=relative):
                self.assertIn(name, index)

    def test_relative_paths_and_markdown_heading_anchors(self):
        docs = [ROOT / "README.md", ROOT / "AGENTS.md",
                *sorted((ROOT / "docs").rglob("*.md"))]
        content_cache = {p.resolve(): p.read_text(encoding="utf-8") for p in docs}
        anchor_cache = {p: heading_anchors(body)
                        for p, body in content_cache.items()}
        checked = 0
        failures = []

        for source, body in content_cache.items():
            for line_number, line in non_fenced_lines(body):
                for match in LINK.finditer(line):
                    raw = match.group(1).strip("<>")
                    link = urlsplit(raw)
                    if link.scheme or link.netloc or raw.startswith("//"):
                        continue  # Absolute public platform references are out of scope.
                    path = unquote(link.path)
                    if path.startswith("/"):
                        failures.append(f"{source.relative_to(ROOT)}:{line_number}: "
                                        f"root-absolute link {raw!r}")
                        continue
                    target = source if not path else (source.parent / path).resolve()
                    if not target.is_relative_to(ROOT):
                        failures.append(f"{source.relative_to(ROOT)}:{line_number}: "
                                        f"path escapes repository {raw!r}")
                        continue
                    checked += 1
                    if not target.exists():
                        failures.append(f"{source.relative_to(ROOT)}:{line_number}: "
                                        f"missing target {raw!r}")
                        continue
                    fragment = unquote(link.fragment)
                    if not fragment:
                        continue
                    if target.suffix.lower() != ".md":
                        failures.append(f"{source.relative_to(ROOT)}:{line_number}: "
                                        f"heading anchor on non-Markdown target {raw!r}")
                        continue
                    if target not in anchor_cache:
                        anchor_cache[target] = heading_anchors(
                            target.read_text(encoding="utf-8"))
                    if fragment not in anchor_cache[target]:
                        failures.append(f"{source.relative_to(ROOT)}:{line_number}: "
                                        f"missing heading #{fragment} in "
                                        f"{target.relative_to(ROOT)}")
        self.assertGreater(checked, 25, "expected a connected Markdown navigation graph")
        self.assertFalse(failures, "\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
