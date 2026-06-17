from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.demos.rehearsal import run_rehearsal
from agentos.workers.codex_smoke import SMOKE_LINE


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
            fake_docker = root / "fake-docker"
            fake_docker.write_text(
                "#!/bin/sh\n"
                "artifacts=''\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = '-v' ]; then\n"
                "    shift\n"
                "    case \"$1\" in\n"
                "      *:/agentos/artifacts) artifacts=${1%:/agentos/artifacts} ;;\n"
                "    esac\n"
                "  fi\n"
                "  shift\n"
                "done\n"
                "printf 'rehearsed\\n' > \"$artifacts/readme.txt\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_docker.chmod(0o755)

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
    path.write_text(
        "#!/bin/sh\n"
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "path = Path('README.md')\n"
        "text = path.read_text(encoding='utf-8')\n"
        f"line = {SMOKE_LINE!r}\n"
        "path.write_text(text.replace('\\n\\n', f'\\n\\n{line}\\n\\n', 1), encoding='utf-8')\n"
        "PY\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


if __name__ == "__main__":
    unittest.main()
