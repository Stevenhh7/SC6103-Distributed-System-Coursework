"""A log-auditor regression tests; deliberately synthetic, independent of network results."""
from copy import deepcopy
import unittest
from .run_suite import audit_server
from .analyze_results import EvidenceError

class ServerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.request=dict(event='REQUEST_CREATED',requestId=2,operation=3,encodedHex='original')
        base=dict(sessionId='session',requestId=2,operation=3,mode='AMO',status=0)
        self.events=[dict(base,event='REQUEST_RECEIVED',encodedHex='original'),dict(base,event='BUSINESS_EXECUTED'),
            dict(base,event='HISTORY_SAVED'),dict(base,event='DROP_REPLY'),dict(base,event='REQUEST_RECEIVED',encodedHex='original'),
            dict(base,event='CACHE_HIT'),dict(base,event='REPLY_SENT')]
    def audit(self):return audit_server(self.events,'reply_loss_reserve','amo','session',[self.request])
    def test_correct_amo_evidence_accepted(self):
        self.assertEqual(dict(requestId=2,operation=3,businessExecutions=1,cacheHits=1,dropReplies=1),self.audit()[0])
    def test_missing_execution_cache_receive_save_or_drop_rejected(self):
        original=deepcopy(self.events)
        for name in ['BUSINESS_EXECUTED','CACHE_HIT','REQUEST_RECEIVED','HISTORY_SAVED','DROP_REPLY']:
            self.events=deepcopy(original);self.events.remove(next(e for e in self.events if e['event']==name))
            with self.subTest(name=name),self.assertRaises(EvidenceError):self.audit()
    def test_duplicate_business_execution_rejected(self):
        self.events.append(dict(self.events[1]))
        with self.assertRaises(EvidenceError):self.audit()
    def test_wrong_mode_operation_status_and_bytes_rejected(self):
        original=deepcopy(self.events)
        for index,key,value in [(1,'mode','ALO'),(1,'operation',5),(1,'status',4),(4,'encodedHex','changed')]:
            self.events=deepcopy(original);self.events[index][key]=value
            with self.subTest(key=key),self.assertRaises(EvidenceError):self.audit()
    def test_reply_before_cache_rejected(self):
        self.events[2],self.events[3]=self.events[3],self.events[2]
        with self.assertRaises(EvidenceError):self.audit()
    def test_send_failure_rejected(self):
        self.events.append(dict(self.events[-1],event='REPLY_SEND_FAILED'))
        with self.assertRaises(EvidenceError):self.audit()
