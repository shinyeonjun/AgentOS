from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
