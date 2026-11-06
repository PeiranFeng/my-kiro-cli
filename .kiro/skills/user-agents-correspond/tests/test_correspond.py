import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HELPER = Path(__file__).parents[1] / "scripts" / "correspond.py"

class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "correspondence"
        self.body = Path(self.temp.name) / "body"
    def tearDown(self): self.temp.cleanup()
    def run_helper(self, *args, check=True):
        return subprocess.run([sys.executable, str(HELPER), "--correspondence-dir", str(self.root), *args], text=True, capture_output=True, check=check)
    def work(self, work_id):
        repo, issue, pr, worker = work_id.rsplit("-", 3)
        self.run_helper("update-work", "--work-id", work_id, "--repo", f"/clone/{repo}", "--issue", issue, "--pr", pr, "--sub-worker", worker, "--user-requirement", "Test protocol.", "--progress", "Waiting.")
    def send(self, source, target, body):
        self.body.write_text(body)
        self.run_helper("broadcast", "--work-id", source, "--source-agent", "agent", "--target-work-id", target, "--action", "information", "--body-file", str(self.body))
    def test_watch_is_read_only_and_direct_target_wins(self):
        self.work("repo-_-_-1"); self.work("other-_-_-2"); self.send("other-_-_-2", "repo-_-_-1", "direct")
        state = self.root / "state/active/repo-_-_-1.md"; before = state.read_bytes()
        output = json.loads(self.run_helper("watch", "--work-id", "repo-_-_-1", "--cursor", "none", "--timeout-seconds", "0").stdout)
        self.assertEqual(output["events"][0]["body"], "direct"); self.assertEqual(state.read_bytes(), before)
    def test_broadcast_is_immutable(self):
        self.work("repo-_-_-1"); self.body.write_text("broadcast")
        self.run_helper("broadcast", "--work-id", "repo-_-_-1", "--source-agent", "agent", "--action", "information", "--body-file", str(self.body))
        self.assertEqual(len(list((self.root / "messages").glob("*.md"))), 1)

    def test_own_broadcast_is_ignored(self):
        self.work("repo-_-_-1"); self.send("repo-_-_-1", "broadcast", "own")
        output = json.loads(self.run_helper("watch", "--work-id", "repo-_-_-1", "--cursor", "none", "--timeout-seconds", "0").stdout)
        self.assertEqual(output["events"], [])

    def test_request_event_carries_acknowledgement_and_work(self):
        self.work("repo-_-_-1"); self.work("repo-_-_-2"); self.body.write_text("please acknowledge")
        self.run_helper("broadcast", "--work-id", "repo-_-_-2", "--source-agent", "agent", "--target-work-id", "repo-_-_-1", "--action", "request", "--body-file", str(self.body), "--requested-acknowledgement-from-work-id", "repo-_-_-1", "--requested-acknowledgement", "repo-_-_-1 received")
        output = json.loads(self.run_helper("watch", "--work-id", "repo-_-_-1", "--cursor", "none", "--timeout-seconds", "0").stdout)
        event = output["events"][0]
        self.assertEqual(event["requested_acknowledgement_from_work_id"], "repo-_-_-1")
        self.assertEqual(event["requested_acknowledgement"], "repo-_-_-1 received")
        self.assertEqual(output["work"]["user_requirement"], "Test protocol.")

    def test_state_with_extra_field_is_accepted_and_preserved(self):
        self.work("repo-_-_-1")
        state = self.root / "state/active/repo-_-_-1.md"
        state.write_text(state.read_text().replace("---\n", "---\nlegacy_field: \"kept\"\n", 1))
        self.work("repo-_-_-1")
        self.assertIn('legacy_field: "kept"', state.read_text())

    def test_watch_accepts_call_timestamp(self):
        self.work("repo-_-_-1")
        output = json.loads(self.run_helper("watch", "--work-id", "repo-_-_-1", "--call-timestamp", "2026-11-06T06:40:00Z", "--timeout-seconds", "0").stdout)
        self.assertEqual(output["events"], [])

    def test_archive_then_restore_preserves_state_bytes(self):
        self.work("repo-_-_-1")
        active = self.root / "state/active/repo-_-_-1.md"; archived = self.root / "state/archived/repo-_-_-1.md"
        before = active.read_bytes()
        self.run_helper("archive", "--work-id", "repo-_-_-1")
        self.assertFalse(active.exists()); self.assertEqual(archived.read_bytes(), before)
        self.run_helper("restore", "--work-id", "repo-_-_-1")
        self.assertFalse(archived.exists()); self.assertEqual(active.read_bytes(), before)

    def test_archived_work_is_unusable_until_restored(self):
        self.work("repo-_-_-1"); self.run_helper("archive", "--work-id", "repo-_-_-1")
        repo, issue, pr, worker = "repo", "_", "_", "1"
        update = self.run_helper("update-work", "--work-id", "repo-_-_-1", "--repo", f"/clone/{repo}", "--issue", issue, "--pr", pr, "--sub-worker", worker, "--user-requirement", "Test protocol.", "--progress", "Waiting.", check=False)
        self.assertEqual(update.returncode, 2); self.assertFalse((self.root / "state/active/repo-_-_-1.md").exists())
        watch = self.run_helper("watch", "--work-id", "repo-_-_-1", "--timeout-seconds", "0", check=False)
        self.assertEqual(watch.returncode, 2)

    def test_archive_and_restore_refuse_missing_source_or_existing_target(self):
        self.assertEqual(self.run_helper("archive", "--work-id", "repo-_-_-1", check=False).returncode, 2)
        self.assertEqual(self.run_helper("restore", "--work-id", "repo-_-_-1", check=False).returncode, 2)
        self.work("repo-_-_-1"); self.run_helper("archive", "--work-id", "repo-_-_-1")
        archived = self.root / "state/archived/repo-_-_-1.md"
        active = self.root / "state/active/repo-_-_-1.md"
        active.write_bytes(archived.read_bytes()); archived_before = archived.read_bytes(); active_before = active.read_bytes()
        result = self.run_helper("restore", "--work-id", "repo-_-_-1", check=False)
        self.assertEqual(result.returncode, 2); self.assertEqual(archived.read_bytes(), archived_before); self.assertEqual(active.read_bytes(), active_before)
        result = self.run_helper("archive", "--work-id", "repo-_-_-1", check=False)
        self.assertEqual(result.returncode, 2); self.assertEqual(archived.read_bytes(), archived_before); self.assertEqual(active.read_bytes(), active_before)

if __name__ == "__main__": unittest.main()
