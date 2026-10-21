"""启动准备的边界测试，不触碰真实USB或Windows网络。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import offline_demo
import supervise_bridge
import sys
import subprocess


class PrepareTests(unittest.TestCase):
    def check_prepare(self, mode, microphone=True, reboot=False):
        starts = []
        status_calls = []
        def adb(*args, **kwargs):
            if args[2] == 'push':
                return ''
            command = args[3]
            if command.endswith(' status'):
                status_calls.append(True)
                if mode == 'adb' and len(status_calls) > 1:
                    raise AssertionError('提交切换后不得等待重连或查询状态')
                return json.dumps({'mode': mode if len(status_calls) == 1 else 'ready', 'boot_id': 'original'})
            if command.endswith(' start'):
                starts.append(True)
                return '{"started_pid": 123}'
            if command.endswith(' confirm'):
                return json.dumps({'mode': 'ready', 'boot_id': 'new' if reboot else 'original'})
            if command == 'arecord -l':
                return 'card 2: Device [USB Sound], device 0: USB Audio [USB Audio]' if microphone else ''
            if command == 'ip addr show usb0':
                return 'inet 169.254.113.2/16 scope global usb0'
            raise AssertionError('未预期的板端操作')
        with tempfile.TemporaryDirectory() as directory, patch.object(offline_demo, 'ROOT', Path(directory)), \
             patch.object(offline_demo, 'local_preflight'), patch.object(offline_demo, 'board_connected', return_value=True), \
             patch.object(offline_demo, 'find_rndis_host', return_value='169.254.133.112'), \
             patch.object(offline_demo, 'run_adb', side_effect=adb):
            if mode == 'adb':
                with self.assertRaises(offline_demo.PreparationPending):
                    offline_demo.prepare('adb', '20080411')
                host = None
            else:
                host = offline_demo.prepare('adb', '20080411')
        return host, starts

    def test_pure_adb_is_prepared_once(self):
        host, starts = self.check_prepare('adb')
        self.assertIsNone(host)
        self.assertEqual(len(starts), 1)

    def test_ready_state_is_not_reconfigured(self):
        _, starts = self.check_prepare('ready')
        self.assertFalse(starts)

    def test_usb_transition_exits_without_starting_model(self):
        with patch.object(sys, 'argv', ['offline_demo.py']), \
             patch.object(offline_demo, 'find_adb', return_value='adb'), \
             patch.object(offline_demo, 'prepare', side_effect=offline_demo.PreparationPending('测试替身：等待手动启动')), \
             patch.object(offline_demo.subprocess, 'call') as launch:
            self.assertEqual(offline_demo.main(), 3)
            launch.assert_not_called()

    def test_missing_microphone_stops_preparation(self):
        with self.assertRaisesRegex(RuntimeError, '唯一USB麦克风'):
            self.check_prepare('ready', microphone=False)

    def test_board_reboot_stops_preparation(self):
        with self.assertRaisesRegex(RuntimeError, '开发板重启'):
            self.check_prepare('ready', reboot=True)

    def test_unknown_mode_is_not_reconfigured(self):
        with self.assertRaisesRegex(RuntimeError, '未知USB状态'):
            self.check_prepare('unknown')

    def test_prepare_failure_does_not_start_model(self):
        with patch.object(sys, 'argv', ['offline_demo.py', '--prepare-only']), \
             patch.object(offline_demo, 'find_adb', return_value='adb'), \
             patch.object(offline_demo, 'prepare', side_effect=RuntimeError('测试替身：麦克风缺失')), \
             patch.object(offline_demo.subprocess, 'call') as launch:
            self.assertEqual(offline_demo.main(), 2)
            launch.assert_not_called()

    @patch('supervise_bridge.supervise', return_value=0)
    @patch('supervise_bridge.subprocess.Popen')
    @patch('supervise_bridge.board_connected', return_value=True)
    def test_prepare_only_is_guarded_and_does_not_start_model(self, connected, spawn, monitor):
        with patch.object(sys, 'argv', ['supervise_bridge.py', '--adb', 'adb', '--prepare-only']):
            self.assertEqual(supervise_bridge.main(), 0)
        command = spawn.call_args.args[0]
        self.assertTrue(command[2].endswith('offline_demo.py'))
        self.assertIn('--prepare-only', command)
        self.assertNotIn('--start-xinyu', command)
        monitor.assert_called_once()
