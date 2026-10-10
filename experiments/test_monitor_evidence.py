"""Regression for R2: these are synthetic evidence checks, not real UDP tests."""
from copy import deepcopy
import unittest
from .analyze_results import analyze, EvidenceError
from .test_analyze_results import client_evidence
from client.tests.helpers import SESSION

class MonitorEvidenceTests(unittest.TestCase):
    def run_evidence(self, edit):
        for mode in ('alo', 'amo'):
            with self.subTest(mode=mode):
                events, code, proxy = client_evidence('monitor', mode)
                edit(events)
                yield events, mode, code, proxy

    def test_early_end_rejected(self):
        def edit(events):
            start = next(e for e in events if e['event'] == 'MONITOR_START')
            next(e for e in events if e['event'] == 'MONITOR_END')['monotonic'] = start['monotonic']
        for events, mode, code, proxy in self.run_evidence(edit):
            with self.assertRaises(EvidenceError): analyze(events, 'monitor', mode, SESSION, code, proxy)

    def test_missing_invalid_and_nonfinite_times_rejected(self):
        for name, field in [('MONITOR_START', 'monotonic'), ('MONITOR_START', 'deadline'), ('MONITOR_END', 'monotonic')]:
            for value in [None, '101.2', True, float('nan'), float('inf')]:
                events, code, proxy = client_evidence('monitor', 'amo')
                next(e for e in events if e['event'] == name)[field] = value
                with self.subTest(name=name, field=field, value=value), self.assertRaises(EvidenceError):
                    analyze(events, 'monitor', 'amo', SESSION, code, proxy)

    def test_normal_late_and_zero_remaining_accepted(self):
        for mode in ('alo','amo'):
            for zero in (False, True):
                events, code, proxy = client_evidence('monitor', mode)
                start = next(e for e in events if e['event'] == 'MONITOR_START')
                end = next(e for e in events if e['event'] == 'MONITOR_END')
                if zero:
                    next(e for e in events if e['event'] == 'REPLY' and e['requestId'] == 2)['body']['remainingMillis'] = 0
                    start['deadline'] = start['monotonic']
                    end['monotonic'] = start['monotonic']
                else:
                    end['monotonic'] += .01
                self.assertEqual('STATE_VERIFIED_NEEDS_A_LOG_REVIEW', analyze(events, 'monitor', mode, SESSION, code, proxy)['result'])
