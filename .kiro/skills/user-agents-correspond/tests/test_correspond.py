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

if __name__ == "__main__": unittest.main()
