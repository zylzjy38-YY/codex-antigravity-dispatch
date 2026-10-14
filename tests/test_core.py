import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_antigravity_dispatch import core
from codex_antigravity_dispatch.storage import Invalid, initialize, read_json


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "state"
        initialize(self.root)
        self.work = self.base / "project with 空格"
        self.work.mkdir()
        self.source = self.work / "input.txt"
        self.source.write_text("unchanged", encoding="utf-8")
        self.task = {"goal": "离线验证", "background": "Test task packaging", "domain": "hard_knowledge",
                     "work_dir": str(self.work), "inputs": [str(self.source)], "access": "read-only",
                     "allowed_write_paths": [], "acceptance": ["Produce verifiable evidence"],
                     "constraints": ["Do not change files"], "network": "none"}

    def prepare(self, task=None, mode="auto"):
        return core.prepare(self.task if task is None else task, mode, self.root)

    def test_init_does_not_overwrite_existing_state(self):
        before = (self.root / "config.json").read_bytes()
        with self.assertRaises(Invalid):
            initialize(self.root)
        self.assertEqual(before, (self.root / "config.json").read_bytes())

    def test_complete_offline_flow_has_no_external_effect(self):
        with patch("subprocess.Popen", side_effect=AssertionError("No process")), \
             patch("socket.create_connection", side_effect=AssertionError("No network")):
            record, code = self.prepare()
            self.assertEqual(code, 0)
            self.assertEqual(core.inspect(record["run_id"], self.root)["status"], "prepared_offline")
            blocked, code = core.dispatch(record["run_id"], self.root)
            self.assertEqual(code, 3)
            self.assertFalse(blocked["execution_performed"])
            self.assertFalse(core.status(self.root)["enabled"])
        self.assertEqual(self.source.read_text(), "unchanged")
        self.assertEqual(list(self.work.iterdir()), [self.source])

    def test_all_nine_domains_and_three_modes(self):
        preferred = {"frontend_visual":"antigravity", "frontend_implementation":"antigravity",
                     "complex_deliverables":"antigravity", "hard_knowledge":"antigravity",
                     "engineering":"codex", "research_verification":"ask_user", "saas_workflows":"ask_user",
                     "scientific_code":"ask_user", "document_reasoning":"ask_user"}
        for domain, executor in preferred.items():
            for mode, expected in (("auto", executor), ("independent", "codex"), ("antigravity", "antigravity")):
                with self.subTest(domain=domain, mode=mode):
                    self.assertEqual(core.route(domain, mode, self.root)["recommended_executor"], expected)

    def test_non_delegated_tasks_create_no_package(self):
        for domain, mode in (("engineering", "auto"), ("hard_knowledge", "independent"), ("document_reasoning", "auto")):
            result, code = self.prepare({**self.task, "domain": domain}, mode)
            self.assertEqual((result["status"], code), ("not_prepared", 4))
        self.assertFalse((self.root / "runs").exists())

    def test_invalid_tasks_fail_before_creating_run(self):
        cases = [{"goal":" "}, {"acceptance":[]}, {"constraints":[]}, {"domain":"unknown"},
                 {"inputs":"string"}, {"inputs":[str(self.work / 'missing')]}, {"work_dir":"relative"},
                 {"work_dir":str(self.source)}, {"network":"all"}, {"access":"write"},
                 {"allowed_write_paths":[str(self.work / 'out.txt')]}]
        for update in cases:
            with self.subTest(update=update), self.assertRaises((Invalid, OSError)):
                self.prepare({**self.task, **update})
        for value in ([], None, {}, {**self.task, "model":"other"}):
            if value is None:
                with self.assertRaises(Invalid):
                    core.validate_task(value, self.root)
            else:
                with self.assertRaises(Invalid):
                    self.prepare(value)
        self.assertFalse((self.root / "runs").exists())

    def test_scoped_writes_and_state_protection(self):
        task = {**self.task, "access":"write", "allowed_write_paths":[str(self.work / 'src' / 'new.py')]}
        self.assertEqual(self.prepare(task)[1], 0)
        for path in (self.work, self.work / '..' / 'outside', self.root):
            with self.subTest(path=path), self.assertRaises(Invalid):
                self.prepare({**task, "allowed_write_paths":[str(path)]})
        with self.assertRaises(Invalid):
            self.prepare({**task, "work_dir":str(self.base), "allowed_write_paths":[str(self.root / 'config.json')]})
        self.assertFalse((self.work / 'src').exists())

    def test_preparation_metadata_cannot_claim_execution(self):
        record, _ = self.prepare()
        meta = Path(record['run_dir']) / 'meta.json'
        original = read_json(meta)
        for key, value in (("status","completed"), ("execution_performed",True), ("auto_resume",True),
                           ("verified_model","fake"), ("observed_changes",[]), ("usage",{}), ("run_id","wrong"),
                           ("schema_version",True)):
            with self.subTest(key=key):
                meta.write_text(json.dumps({**original, key:value}), encoding='utf-8')
                with self.assertRaises(Invalid):
                    core.inspect(record['run_id'], self.root)
        meta.write_text(json.dumps(original), encoding='utf-8')
        self.assertEqual(core.inspect(record['run_id'], self.root)['run_id'], record['run_id'])

    def test_task_edit_and_path_traversal_are_rejected(self):
        record, _ = self.prepare()
        path = Path(record['run_dir']) / 'task.json'
        task = read_json(path)
        path.write_text(json.dumps({**task, 'goal':'changed'}), encoding='utf-8')
        with self.assertRaisesRegex(Invalid, 'changed'):
            core.inspect(record['run_id'], self.root)
        for run_id in ('../config.json', '..\\config.json', str(self.root), ''):
            with self.assertRaises(Invalid):
                core.inspect(run_id, self.root)

    def test_malformed_configuration_is_not_silently_accepted(self):
        cfg_path = self.root / 'config.json'
        original = read_json(cfg_path)
        for value in ([], {}, {**original, 'enabled':'false'}, {**original, 'schema_version':True},
                      {**original, 'model_id':42}, {**original, 'adapter':'arbitrary-command'}):
            cfg_path.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaises(Invalid):
                core.status(self.root)

    def test_enabling_flag_does_not_activate_production(self):
        cfg_path = self.root / 'config.json'
        cfg = read_json(cfg_path)
        cfg_path.write_text(json.dumps({**cfg, 'enabled':True}), encoding='utf-8')
        self.assertEqual(core.status(self.root)['status'], 'blocked')
        record, _ = self.prepare()
        self.assertEqual(core.dispatch(record['run_id'], self.root)[1], 3)

    def test_unknown_policy_executor_is_rejected(self):
        path = self.root / 'routing.json'
        value = read_json(path)
        value['domains']['hard_knowledge']['preferred_executor'] = 'other-model'
        path.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaises(Invalid):
            self.prepare()

    def test_symlink_in_state_is_rejected_when_supported(self):
        link = self.base / 'state-link'
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation not permitted on this host')
        with self.assertRaises(Invalid):
            core.status(link)

    def test_failed_prepare_does_not_publish_partial_run(self):
        with patch.object(core, 'write_json', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertEqual(list((self.root / 'runs').iterdir()), [])

    def test_json_size_limit(self):
        path = self.base / 'large.json'
        path.write_bytes(b' ' * (2 * 1024 * 1024 + 1))
        with self.assertRaises(Invalid):
            read_json(path)


if __name__ == '__main__':
    unittest.main()
