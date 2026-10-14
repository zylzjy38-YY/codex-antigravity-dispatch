import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from codex_antigravity_dispatch import core, runner
from codex_antigravity_dispatch.storage import Invalid, initialize, read_json


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'state'
        initialize(self.root)
        self.work = self.base / 'work'
        self.work.mkdir()
        self.task = {'goal':'Reply hello', 'background':'Text probe', 'domain':'hard_knowledge',
                     'work_dir':str(self.work), 'inputs':[], 'access':'read-only',
                     'allowed_write_paths':[], 'acceptance':['A hello response'],
                     'constraints':['No tools'], 'network':'none'}
        self.record, _ = core.prepare(self.task, 'auto', self.root)
        self.payload = {'status':'SUCCESS', 'conversation_id':'fake-test-session',
                        'structured_output':{'summary':'hello', 'blockers':[], 'evidence':[]},
                        'usage':{'total_tokens':1}}

    def run_test(self, **overrides):
        kwargs = dict(run_id=self.record['run_id'], root=self.root, model='test-model',
                      agy=sys.executable, timeout=10, allow_execution=True)
        return runner.run_test(**{**kwargs, **overrides})

    def fake_invoke(self, argv, cwd, output, errors, timeout):
        self.assertEqual(argv[argv.index('--model') + 1], 'test-model')
        self.assertNotIn('--dangerously-skip-permissions', argv)
        self.assertIn('--sandbox', argv)
        self.assertNotIn(str(self.work), argv[2])
        self.assertEqual(list(cwd.iterdir()), [])
        output.write_text(json.dumps(self.payload), encoding='utf-8')
        errors.write_text('', encoding='utf-8')
        return {'exit_code':0, 'timed_out':False, 'interrupted':False, 'local_process_stopped':True,
                'cli_started':True, 'local_process_tree_stopped':None, 'cleanup_required':False}

    def test_explicit_consent_required_before_any_process(self):
        with patch.object(runner, 'invoke', side_effect=AssertionError('Must not run')):
            result, code = self.run_test(allow_execution=False)
        self.assertEqual((result['status'], code), ('blocked', 3))
        self.assertFalse((self.root / 'execution.lock').exists())

    def test_success_keeps_target_and_reports_unverified_actual_model(self):
        before = (self.root / 'config.json').read_bytes()
        with patch.object(runner, 'invoke', side_effect=self.fake_invoke):
            result, code = self.run_test()
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'response_received')
        self.assertIsNone(result['verified_model'])
        self.assertEqual(result['requested_model'], 'test-model')
        self.assertEqual(before, (self.root / 'config.json').read_bytes())
        self.assertFalse((self.root / 'execution.lock').exists())
        self.assertEqual(list(self.work.iterdir()), [])

    def test_duplicate_attempt_is_not_replayed(self):
        with patch.object(runner, 'invoke', side_effect=self.fake_invoke) as invoke:
            self.run_test()
            with self.assertRaisesRegex(Invalid, 'already'):
                self.run_test()
            self.assertEqual(invoke.call_count, 1)

    def test_lock_refuses_concurrent_execution(self):
        (self.root / 'execution.lock').write_text('existing-run')
        with patch.object(runner, 'invoke', side_effect=AssertionError('Must not run')):
            result, code = self.run_test()
        self.assertEqual((result['status'], code), ('busy', 10))
        self.assertEqual((self.root / 'execution.lock').read_text(), 'existing-run')

    def test_bad_model_and_timeout_rejected(self):
        for overrides in ({'model':'x; echo bad'}, {'model':'--model'}, {'timeout':0}, {'timeout':901}):
            with self.subTest(overrides=overrides), self.assertRaises(Invalid):
                self.run_test(**overrides)

    def test_file_tasks_cannot_use_text_probe(self):
        source = self.work / 'input.txt'
        source.write_text('data')
        for update in ({'inputs':[str(source)]}, {'network':'research'},
                       {'access':'write', 'allowed_write_paths':[str(self.work / 'output.txt')]}):
            record, _ = core.prepare({**self.task, **update}, 'auto', self.root)
            with self.assertRaisesRegex(Invalid, 'Integration probes'):
                self.run_test(run_id=record['run_id'])

    def test_cli_zero_exit_is_not_sufficient(self):
        cases = [('AGY_ERROR: {"message":"denied"}', self.payload),
                 ('Permission request denied', self.payload),
                 ('', {**self.payload, 'status':'ERROR'}),
                 ('', {**self.payload, 'structured_output':{'summary':'missing fields'}})]
        for stderr, payload in cases:
            with self.subTest(stderr=stderr, payload=payload):
                status, _ = runner.parse_response(payload, stderr, 0)
                self.assertNotEqual(status, 'response_received')

    def test_blockers_are_not_success(self):
        self.payload['structured_output']['blockers'] = ['Missing input']
        with patch.object(runner, 'invoke', side_effect=self.fake_invoke):
            result, code = self.run_test()
        self.assertEqual((result['status'], code), ('response_with_blockers', 5))

    def test_malformed_json_is_recorded_as_adapter_error(self):
        def invalid(argv, cwd, output, errors, timeout):
            outcome = self.fake_invoke(argv, cwd, output, errors, timeout)
            output.write_text('not json')
            return outcome
        with patch.object(runner, 'invoke', side_effect=invalid):
            result, code = self.run_test()
        self.assertEqual((result['status'], code), ('adapter_error', 5))
        self.assertTrue(result['execution_performed'])

    def test_unexpected_workspace_writes_fail_probe(self):
        def changing(argv, cwd, output, errors, timeout):
            outcome = self.fake_invoke(argv, cwd, output, errors, timeout)
            (cwd / 'unexpected.txt').write_text('unexpected')
            return outcome
        with patch.object(runner, 'invoke', side_effect=changing):
            result, code = self.run_test()
        self.assertEqual((result['status'], code), ('workspace_changed', 5))

    def test_unconfirmed_termination_keeps_lock(self):
        outcome = {'exit_code':None, 'timed_out':True, 'interrupted':False, 'local_process_stopped':False,
                   'cli_started':True, 'local_process_tree_stopped':False, 'cleanup_required':True}
        with patch.object(runner, 'invoke', return_value=outcome):
            result, code = self.run_test()
        self.assertEqual((result['status'], code), ('timed_out', 6))
        self.assertTrue((self.root / 'execution.lock').exists())
        self.assertFalse(result['remote_cancellation_verified'])

    def test_parent_exit_alone_does_not_release_timeout_lock(self):
        outcome = {'exit_code':-1, 'timed_out':True, 'interrupted':False, 'local_process_stopped':True,
                   'cli_started':True, 'local_process_tree_stopped':False, 'cleanup_required':True}
        with patch.object(runner, 'invoke', return_value=outcome):
            result, code = self.run_test()
        self.assertEqual(code, 6)
        self.assertTrue(result['execution_lock_retained'])
        self.assertTrue((self.root / 'execution.lock').exists())

    def test_wait_error_after_start_is_cleaned_and_reported(self):
        process = Mock(pid=12345, returncode=-1)
        process.wait.side_effect = OSError('wait failed')
        with patch.object(runner.subprocess, 'Popen', return_value=process), \
             patch.object(runner, 'stop_process', return_value={
                 'local_process_stopped':False, 'local_process_tree_stopped':False}) as stop:
            result = runner.invoke(['fake'], self.work, self.base / 'out', self.base / 'err', 10)
        stop.assert_called_once_with(process)
        self.assertTrue(result['cli_started'])
        self.assertFalse(result['local_process_stopped'])

    def test_save_failure_preserves_execution_outcome(self):
        real_write = runner.write_json
        def failing_result(path, value):
            if path.name == 'result.json':
                raise OSError('disk full')
            real_write(path, value)
        with patch.object(runner, 'invoke', side_effect=self.fake_invoke), \
             patch.object(runner, 'write_json', side_effect=failing_result):
            result, code = self.run_test()
        self.assertEqual((result['status'], code), ('result_persistence_failed', 5))
        self.assertTrue(result['execution_performed'])
        self.assertEqual(result['outcome_status'], 'response_received')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows taskkill behavior')
    def test_failed_tree_kill_never_claims_tree_stopped(self):
        process = Mock(pid=12345)
        process.poll.side_effect = [None, None, 1]
        with patch.object(runner.subprocess, 'run', return_value=Mock(returncode=1)):
            result = runner.stop_process(process)
        self.assertTrue(result['local_process_stopped'])
        self.assertFalse(result['local_process_tree_stopped'])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows taskkill behavior')
    def test_parent_already_exited_is_not_targeted_by_pid(self):
        process = Mock(pid=12345)
        process.poll.return_value = 0
        with patch.object(runner.subprocess, 'run') as taskkill:
            result = runner.stop_process(process)
        taskkill.assert_not_called()
        self.assertFalse(result['local_process_tree_stopped'])

    def test_process_invocation_captures_output_without_shell(self):
        output, errors = self.base / 'stdout', self.base / 'stderr'
        outcome = runner.invoke([sys.executable, '-c', 'print("fake provider output")'], self.work, output, errors, 10)
        self.assertEqual(outcome['exit_code'], 0)
        self.assertEqual(output.read_text().strip(), 'fake provider output')

    def test_real_local_process_timeout(self):
        output, errors = self.base / 'stdout', self.base / 'stderr'
        outcome = runner.invoke([sys.executable, '-c', 'import time; time.sleep(30)'], self.work, output, errors, 0.1)
        self.assertTrue(outcome['timed_out'])
        self.assertTrue(outcome['local_process_stopped'])


if __name__ == '__main__':
    unittest.main()
