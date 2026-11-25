"""Tests of the repository itself: version, example project, changelog script, doc links, pinned workflow actions.
They need the repository checkout (README, docs, examples), so they skip themselves in an installed copy of the skill.
Run: python -m unittest test_project   (from the tools folder)"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HAS_REPO = (REPO / "README.md").is_file() and (REPO / "docs").is_dir() and (REPO / "examples").is_dir()


def run(*args: str, cwd: Path | None = None):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=cwd)


class VersionTests(unittest.TestCase):
    def test_check_reports_the_version_file(self):
        p = run(str(REPO / "tools" / "check.py"), "--version")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), (REPO / "VERSION").read_text(encoding="utf-8").strip())
        self.assertRegex(p.stdout.strip(), r"^\d+\.\d+\.\d+$")

    def test_installer_copies_the_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(str(REPO / "install.py"), "--skills-dir", str(Path(tmp) / "s"), "--agents-dir", str(Path(tmp) / "a"))
            self.assertEqual((Path(tmp) / "s" / "tracespec" / "VERSION").read_text(encoding="utf-8").strip(),
                             (REPO / "VERSION").read_text(encoding="utf-8").strip())


@unittest.skipUnless(HAS_REPO, "needs the repository checkout")
class RepositoryTests(unittest.TestCase):
    def test_the_version_has_a_changelog_section(self):
        version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
        p = run(str(REPO / "scripts" / "changelog_section.py"), version)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("###", p.stdout)
        self.assertNotEqual(run(str(REPO / "scripts" / "changelog_section.py"), "99.99.99").returncode, 0)

    def test_the_example_project_audits_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "shop"
            shutil.copytree(REPO / "examples" / "shop", proj)
            p = run(str(REPO / "tools" / "check.py"), str(proj), "--audit", "--no-run")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("0 error(s)", p.stdout)
            # and the trace answers a real question about it
            p = run(str(REPO / "tools" / "check.py"), str(proj), "--trace", "SHOP-31")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("FR-3", p.stdout)

    def test_the_example_has_no_transient_files(self):
        found = [p.relative_to(REPO).as_posix() for p in (REPO / "examples").rglob("*")
                 if p.name in (".tracespec-junit.xml", ".tracespec-check.json", "__pycache__", ".pytest_cache", "current.db")]
        self.assertEqual(found, [])

    def test_relative_links_in_the_markdown_files_resolve(self):
        files = [p for p in (list(REPO.glob("*.md")) + list((REPO / "docs").rglob("*.md")) + list((REPO / ".github").rglob("*.md")))]
        link = re.compile(r"\]\((?!https?:|mailto:|#)([^)\s#]+)(?:#[^)\s]*)?\)")
        broken = []
        for f in files:
            text = re.sub(r"```.*?```", "", f.read_text(encoding="utf-8"), flags=re.S)       # not inside code blocks
            for m in link.finditer(text):
                target = (f.parent / m.group(1)).resolve()
                if not target.exists():
                    broken.append(f"{f.relative_to(REPO).as_posix()} -> {m.group(1)}")
        self.assertEqual(broken, [])

    def test_workflow_actions_are_pinned_to_a_commit(self):
        unpinned = []
        for wf in (REPO / ".github" / "workflows").glob("*.yml"):
            text = wf.read_text(encoding="utf-8")
            self.assertNotIn("pull_request_target", text, wf.name)
            for line in text.splitlines():
                m = re.match(r"\s*-?\s*uses:\s*(\S+)", line)
                if m and not re.search(r"@[0-9a-f]{40}$", m.group(1)):
                    unpinned.append(f"{wf.name}: {m.group(1)}")
        self.assertEqual(unpinned, [])

    def test_issue_forms_and_templates_exist(self):
        for rel in (".github/ISSUE_TEMPLATE/bug_report.yml", ".github/ISSUE_TEMPLATE/feature_request.yml",
                    ".github/ISSUE_TEMPLATE/docs.yml", ".github/ISSUE_TEMPLATE/config.yml", ".github/PULL_REQUEST_TEMPLATE.md",
                    ".github/CODEOWNERS", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "CHANGELOG.md", "LICENSE"):
            self.assertTrue((REPO / rel).is_file(), rel)

    def test_no_machine_specific_paths_or_other_skills_are_referenced(self):
        offenders = []
        for f in list(REPO.rglob("*.md")) + list(REPO.rglob("*.py")) + list(REPO.rglob("*.yml")):
            if ".git" in f.parts or f.name == "test_project.py" or "examples" in f.parts:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for needle in ("C:/Users/", "C:\\Users\\", "service-build-loop", "icron"):
                if needle.lower() in text.lower():
                    offenders.append(f"{f.relative_to(REPO).as_posix()}: {needle}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
