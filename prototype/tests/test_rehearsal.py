from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.demos.rehearsal import run_rehearsal
from agentos.workers.codex_smoke import SMOKE_LINE
from fake_tools import write_python_tool


class AgentOSRehearsalTests(unittest.TestCase):
    def test_rehearsal_can_skip_docker(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_rehearsal(
                state_dir=root / "state",
                output_dir=root / "output",
                skip_docker=True,
            )

            self.assertTrue(result.passed)
            self.assertTrue(result.summary_path.exists())
            self.assertEqual([step.name for step in result.steps], [
                "code_fix_lifecycle",
                "markdown_document_lifecycle",
                "real_worker_codex_smoke",
                "docker_sandbox_policy",
            ])
            self.assertEqual(result.steps[-1].status, "skipped")
            self.assertEqual(result.steps[-2].status, "skipped")

            summary = json.loads(result.summary_path.read_text())
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["steps"][-1]["status"], "skipped")
            self.assertEqual(summary["steps"][-2]["status"], "skipped")

    def test_rehearsal_runs_fake_docker_policy_step(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_docker = write_python_tool(
                root / "fake-docker",
                "from pathlib import Path\n"
                "import sys\n"
                "artifacts = None\n"
                "args = sys.argv[1:]\n"
                "for index, value in enumerate(args[:-1]):\n"
                "    if value == '-v' and args[index + 1].endswith(':/agentos/artifacts'):\n"
                "        artifacts = args[index + 1][:-len(':/agentos/artifacts')]\n"
                "if artifacts:\n"
                "    Path(artifacts, 'readme.txt').write_text('rehearsed\\n', encoding='utf-8')\n"
                "raise SystemExit(0)\n",
            )

            result = run_rehearsal(
                state_dir=root / "state",
                output_dir=root / "output",
                docker_bin=str(fake_docker),
            )

            self.assertTrue(result.passed)
            self.assertEqual(result.steps[-1].name, "docker_sandbox_policy")
            self.assertEqual(result.steps[-1].status, "passed")
            self.assertIn("policy", result.steps[-1].artifacts)
            summary = json.loads(result.summary_path.read_text())
            self.assertEqual(summary["steps"][-1]["status"], "passed")

    def test_rehearsal_can_include_real_worker_step(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_codex = _write_fake_codex(root / "fake-codex")

            result = run_rehearsal(
                state_dir=root / "state",
                output_dir=root / "output",
                skip_docker=True,
                include_real_worker=True,
                codex_bin=str(fake_codex),
            )

            self.assertTrue(result.passed)
            real_worker = result.steps[2]
            self.assertEqual(real_worker.name, "real_worker_codex_smoke")
            self.assertEqual(real_worker.status, "passed")
            self.assertIn("worker_result", real_worker.artifacts)


def _write_fake_codex(path: Path) -> Path:
    return write_python_tool(
        path,
        "from pathlib import Path\n"
        "path = Path('README.md')\n"
        "text = path.read_text(encoding='utf-8')\n"
        f"line = {SMOKE_LINE!r}\n"
        "path.write_text(text.replace('\\n\\n', f'\\n\\n{line}\\n\\n', 1), encoding='utf-8')\n",
    )


if __name__ == "__main__":
    unittest.main()
