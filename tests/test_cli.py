import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / 'state'

    def command(self, *args):
        completed = subprocess.run([sys.executable, '-m', 'codex_antigravity_dispatch',
                                    '--state-dir', str(self.state), *args],
                                   capture_output=True, encoding='utf-8', timeout=15, check=False)
        self.assertNotIn('Traceback', completed.stderr)
        return completed.returncode, json.loads(completed.stdout)

    def test_installed_cli_offline_round_trip(self):
        self.assertEqual(self.command('init')[0], 0)
        self.assertEqual(self.command('status')[1]['status'], 'disabled')
        task = {'goal':'Reply hello', 'background':'CLI test', 'domain':'hard_knowledge',
                'work_dir':str(self.base), 'inputs':[], 'access':'read-only', 'allowed_write_paths':[],
                'acceptance':['A response'], 'constraints':['No tools'], 'network':'none'}
        path = self.base / 'task.json'
        path.write_text(json.dumps(task), encoding='utf-8')
        code, prepared = self.command('prepare', '--task', str(path), '--mode', 'auto')
        self.assertEqual(code, 0)
        self.assertEqual(self.command('inspect', '--run-id', prepared['run_id'])[1]['status'], 'prepared_offline')
        code, blocked = self.command('dispatch', '--run-id', prepared['run_id'])
        self.assertEqual((code, blocked['execution_performed']), (3, False))
        code, blocked = self.command('run', '--run-id', prepared['run_id'], '--test-model', 'fake')
        self.assertEqual((code, blocked['execution_performed']), (3, False))

    def test_invalid_json_returns_machine_readable_error(self):
        self.command('init')
        path = self.base / 'bad.json'
        path.write_text('{bad')
        code, result = self.command('prepare', '--task', str(path), '--mode', 'auto')
        self.assertEqual((code, result['status'], result['execution_performed']), (2, 'invalid', False))

    def test_missing_state_is_not_silently_created(self):
        code, result = self.command('status')
        self.assertEqual((code, result['status']), (2, 'invalid'))
        self.assertFalse(self.state.exists())


if __name__ == '__main__':
    unittest.main()
