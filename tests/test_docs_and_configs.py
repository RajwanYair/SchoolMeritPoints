#!/usr/intel/bin/python3
"""Tests for documentation (README.md, spec.md, CONTRIBUTING.md, SECURITY.md), SVGs, PWA manifest, and CI configs."""

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestDocsAndConfigs(unittest.TestCase):
    """Validate all documentation, configuration files, SVG diagrams, and API/doc parity."""

    def test_01_manifest_webmanifest(self):
        """Verify manifest.webmanifest is valid JSON with multi-device orientation='any' and relative paths."""
        manifest_path = ROOT_DIR / "manifest.webmanifest"
        self.assertTrue(manifest_path.is_file())
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        for key in ("name", "short_name", "start_url", "display", "orientation", "background_color", "theme_color", "icons"):
            self.assertIn(key, data, f"Missing '{key}' in manifest.webmanifest")

        self.assertEqual(data["orientation"], "any", "manifest.webmanifest must allow any orientation for PC/Tablet/Mobile")
        self.assertEqual(data["start_url"], "./")
        self.assertTrue(len(data["icons"]) >= 1)
        icon_src = data["icons"][0]["src"]
        self.assertEqual(icon_src, "./icon.svg")
        self.assertTrue((ROOT_DIR / "icon.svg").is_file())

    def test_02_svg_diagrams_and_icons_valid_xml(self):
        """Verify icon.svg and all assets/*.svg files are well-formed XML with <svg> root and viewBox."""
        expected_svgs = [
            ROOT_DIR / "icon.svg",
            ROOT_DIR / "assets" / "hero-banner.svg",
            ROOT_DIR / "assets" / "system-flow.svg",
            ROOT_DIR / "assets" / "ui-preview.svg",
            ROOT_DIR / "assets" / "user-journey.svg",
            ROOT_DIR / "assets" / "roadmap-sprints.svg",
        ]
        for svg_path in expected_svgs:
            self.assertTrue(svg_path.is_file(), f"Missing SVG file: {svg_path}")
            tree = ET.parse(svg_path)
            root = tree.getroot()
            self.assertTrue(root.tag.endswith("svg"), f"{svg_path.name} root tag is not <svg>")
            self.assertIn("viewBox", root.attrib, f"{svg_path.name} missing viewBox attribute")

    def test_03_readme_links_mermaid_diagrams_and_api_table_parity(self):
        """Verify README.md local links resolve, Mermaid diagrams exist, and all server.py /api/* routes are documented."""
        readme = (ROOT_DIR / "README.md").read_text(encoding="utf-8")

        # Check Mermaid diagrams
        self.assertIn("```mermaid", readme)
        self.assertIn("sequenceDiagram", readme)
        self.assertIn("flowchart LR", readme)
        self.assertIn("erDiagram", readme)

        # Check all local markdown links and <img src="..."> resolve
        img_srcs = re.findall(r'<img\s+[^>]*src="([^"]+)"', readme)
        md_links = re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", readme)
        for target in img_srcs + md_links:
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            target_path = (ROOT_DIR / target).resolve()
            self.assertTrue(target_path.exists(), f"Broken local link/asset in README.md: {target}")

        # Verify all primary /api/* endpoints are documented in README.md and supported in index.html
        index_html = (ROOT_DIR / "index.html").read_text(encoding="utf-8")
        core_endpoints = [
            "/api/login",
            "/api/logout",
            "/api/me",
            "/api/kiosk",
            "/api/dashboard",
            "/api/users",
            "/api/classes",
            "/api/criteria",
            "/api/entries",
            "/api/rankings/classes",
            "/api/rankings/students",
            "/api/student-score",
            "/api/class-score",
            "/api/history",
            "/api/export",
        ]
        for ep in core_endpoints:
            self.assertIn(ep, readme, f"Endpoint {ep} missing from README.md API documentation")
            self.assertIn(ep, index_html, f"Endpoint {ep} missing from index.html client/demo router")

    def test_04_companion_docs_and_git_ci_configs(self):
        """Verify spec.md, ROADMAP.md, CONTRIBUTING.md, SECURITY.md, LICENSE, .gitignore, .nojekyll, and GitHub workflows."""
        for doc_name in ("spec.md", "ROADMAP.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE", ".gitignore", ".nojekyll"):
            p = ROOT_DIR / doc_name
            self.assertTrue(p.is_file(), f"Missing required repository file: {doc_name}")
            if doc_name != ".nojekyll":
                self.assertGreater(len(p.read_text(encoding="utf-8").strip()), 100)

        gitignore = (ROOT_DIR / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("*.db", "*.db-wal", "*.db-shm", "__pycache__/", ".env"):
            self.assertIn(pattern, gitignore, f"Missing '{pattern}' in .gitignore")

        ci_yml = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("unittest", ci_yml, "ci.yml must execute the unittest suite")
        self.assertIn("workflow_dispatch", ci_yml, "ci.yml should support manual workflow_dispatch")

        pages_yml = (ROOT_DIR / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("deploy-pages", pages_yml)

        release_yml = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("gh release", release_yml)

    def test_05_roadmap_tasks_issues_and_links(self):
        """Verify ROADMAP.md tracks all SMP-xxx sprint tasks, ISS-xxx issues, and valid local links."""
        roadmap = (ROOT_DIR / "ROADMAP.md").read_text(encoding="utf-8")

        for task_id in (
            "SMP-101", "SMP-106", "SMP-107", "SMP-108", "SMP-109",
            "SMP-201", "SMP-205", "SMP-301", "SMP-304",
            "SMP-401", "SMP-403", "SMP-501", "SMP-504",
            "SMP-601", "SMP-603", "SMP-605",
        ):
            self.assertIn(task_id, roadmap, f"Missing sprint task {task_id} in ROADMAP.md")

        for issue_id in (f"ISS-{i:03d}" for i in range(1, 13)):
            self.assertIn(issue_id, roadmap, f"Missing tracked issue {issue_id} in ROADMAP.md")

        md_links = re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", roadmap)
        for target in md_links:
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            target_path = (ROOT_DIR / target).resolve()
            self.assertTrue(target_path.exists(), f"Broken local link in ROADMAP.md: {target}")

    def test_06_vscode_and_copilot_chat_workspace_configs(self):
        """Verify .vscode/*.json, Copilot instructions/prompts/agents, and GitHub issue/PR templates."""
        vscode_files = ("settings.json", "tasks.json", "launch.json", "extensions.json")
        for vf in vscode_files:
            p = ROOT_DIR / ".vscode" / vf
            self.assertTrue(p.is_file(), f"Missing .vscode/{vf}")
            parsed = json.loads(p.read_text(encoding="utf-8"))
            self.assertIsInstance(parsed, dict)

        settings = json.loads((ROOT_DIR / ".vscode" / "settings.json").read_text(encoding="utf-8"))
        self.assertTrue(settings.get("python.testing.unittestEnabled"))
        self.assertTrue(settings.get("github.copilot.chat.codeGeneration.useInstructionFiles"))

        required_github_files = [
            ".github/copilot-instructions.md",
            ".github/prompts/implement-sprint-task.prompt.md",
            ".github/prompts/audit-parity-and-tests.prompt.md",
            ".github/prompts/github-release-check.prompt.md",
            ".github/agents/smp-developer.agent.md",
            ".github/ISSUE_TEMPLATE/config.yml",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/sprint_task.yml",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/dependabot.yml",
        ]
        for rel in required_github_files:
            fp = ROOT_DIR / rel
            self.assertTrue(fp.is_file(), f"Missing GitHub / Copilot config file: {rel}")
            self.assertGreater(len(fp.read_text(encoding="utf-8").strip()), 50)

        # Ensure all repo Markdown files have zero in-file duplicate headings or multiple consecutive blank lines
        for md_path in sorted(ROOT_DIR.rglob("*.md")):
            if ".git" in md_path.parts:
                continue
            txt = md_path.read_text(encoding="utf-8")
            self.assertNotIn("\n\n\n", txt, f"Multiple consecutive blank lines in {md_path.relative_to(ROOT_DIR)}")
            seen_headings = set()
            in_code = False
            for line in txt.splitlines():
                s = line.strip()
                if s.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    continue
                m = re.match(r"^(#{1,4})\s+(.+)", s)
                if m:
                    key = (m.group(1), m.group(2).strip().lower())
                    self.assertNotIn(key, seen_headings, f"Duplicate heading {key} in {md_path.relative_to(ROOT_DIR)}")
                    seen_headings.add(key)


if __name__ == "__main__":
    unittest.main()
