from __future__ import annotations

import unittest
from unittest.mock import patch

from agentos.workers.env_policy import build_worker_env


class WorkerEnvPolicyTests(unittest.TestCase):
    def test_build_worker_env_blocks_non_allowlisted_host_keys(self) -> None:
        worker_env, policy = build_worker_env(
            {"CODEX_HOME": "/tmp/codex"},
            host_env={
                "PATH": "/usr/bin",
                "PATHEXT": ".COM;.EXE;.BAT;.CMD",
                "HOME": "/home/test",
                "AGENTOS_SECRET_TOKEN": "do-not-pass",
            },
        )

        self.assertEqual(worker_env["PATH"], "/usr/bin")
        self.assertEqual(worker_env["PATHEXT"], ".COM;.EXE;.BAT;.CMD")
        self.assertEqual(worker_env["HOME"], "/home/test")
        self.assertEqual(worker_env["CODEX_HOME"], "/tmp/codex")
        self.assertNotIn("AGENTOS_SECRET_TOKEN", worker_env)
        self.assertIn("PATH", policy.inherited_keys)
        self.assertIn("PATHEXT", policy.inherited_keys)
        self.assertIn("CODEX_HOME", policy.override_keys)
        self.assertEqual(policy.blocked_host_key_count, 1)

    def test_windows_worker_env_preserves_case_insensitive_required_keys(self) -> None:
        with patch("agentos.workers.env_policy.platform.system", return_value="Windows"):
            worker_env, policy = build_worker_env(
                host_env={
                    "SYSTEMROOT": "C:\\Windows",
                    "PROGRAMFILES": "C:\\Program Files",
                    "COMSPEC": "C:\\Windows\\System32\\cmd.exe",
                    "PATH": "C:\\Windows\\System32",
                    "AGENTOS_SECRET_TOKEN": "do-not-pass",
                },
            )

        self.assertEqual(worker_env["SystemRoot"], "C:\\Windows")
        self.assertEqual(worker_env["ProgramFiles"], "C:\\Program Files")
        self.assertEqual(worker_env["COMSPEC"], "C:\\Windows\\System32\\cmd.exe")
        self.assertNotIn("AGENTOS_SECRET_TOKEN", worker_env)
        self.assertIn("SystemRoot", policy.inherited_keys)
        self.assertEqual(policy.blocked_host_key_count, 1)

    def test_windows_worker_env_fills_systemroot_from_windir(self) -> None:
        with patch("agentos.workers.env_policy.platform.system", return_value="Windows"):
            worker_env, _policy = build_worker_env(
                host_env={
                    "WINDIR": "C:\\Windows",
                    "PATH": "C:\\Windows\\System32",
                },
            )

        self.assertEqual(worker_env["SystemRoot"], "C:\\Windows")


if __name__ == "__main__":
    unittest.main()
