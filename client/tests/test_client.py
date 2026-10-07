"""菜单、CLI 退出清理与证据日志；测试输出只代表客户端行为。"""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from client.client import main, run_menu
from client.config import ClientConfig
from client.models import CallOutcome, RequestKey
from client.protocol_codec import decode_message
from client.tests.helpers import SESSION, detail, i32, monitor_reply, packet


class MenuInvoker:
    def __init__(self):
        self.config = ClientConfig()
        self.session_id = SESSION
        self.calls = []

    def invoke(self, operation, body):
        self.calls.append((operation, body))
        request_id = len(self.calls)
        if operation == 1:
            raw = packet(i32(1) + i32(1001), op=1, request_id=request_id)
        elif operation == 2:
            raw = detail(request_id=request_id)
        elif operation == 3:
            raw = packet(i32(1001) + i32(8), op=3, request_id=request_id)
        elif operation == 4:
            raw = monitor_reply(0, request_id=request_id)
        else:
            raw = packet(i32(1001) + bytes.fromhex("42f00000"), op=operation, request_id=request_id)
        return CallOutcome(RequestKey(SESSION, request_id), decode_message(raw), 1, False, None, 100.0)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.out, self.err = io.StringIO(), io.StringIO()
        stdout, stderr = redirect_stdout(self.out), redirect_stderr(self.err)
        stdout.__enter__()
        stderr.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)
        self.addCleanup(stderr.__exit__, None, None, None)

    def test_menu_all_operations_and_exit(self):
        invoker = MenuInvoker()
        inputs = ["1", " 北京 ", "SIN", "2", "1001", "3", "1001", "2", "4", "1001", "1",
                  "5", "1001", "120", "6", "1001", "20", "0"]
        with patch("builtins.input", side_effect=inputs), patch("client.client.monitor_until_expiry") as monitor:
            run_menu(invoker)
        self.assertEqual([int(op) for op, _ in invoker.calls], [1, 2, 3, 4, 5, 6])
        self.assertEqual(invoker.calls[0][1].source, "北京")
        monitor.assert_called_once()
        self.assertEqual(monitor.call_args.args[1].deadline_monotonic, 100.0)
        self.assertIn("120.00 SGD", self.out.getvalue())

    def test_invalid_menu_inputs_never_invoke(self):
        invoker = MenuInvoker()
        inputs = ["99", "1", "  ", "3", "1001", "0", "4", "1001", "3601",
                  "5", "1001", "nan", "5", "1001", "1e100", "6", "1001", "1e-50", "0"]
        with patch("builtins.input", side_effect=inputs):
            run_menu(invoker)
        self.assertEqual(invoker.calls, [])
        self.assertEqual(self.out.getvalue().count("输入错误"), 7)

    def test_timeout_text_never_claims_failure_or_auto_retries(self):
        invoker = MenuInvoker()
        invoker.invoke = lambda op, body: CallOutcome(RequestKey(SESSION, 1), None, 5, True, None, None)
        with patch("builtins.input", side_effect=["3", "1001", "1", "0"]):
            run_menu(invoker)
        self.assertIn("执行结果未知", self.out.getvalue())

    def test_check_is_offline_and_closes(self):
        with patch("socket.socket", side_effect=AssertionError("network used")), \
                patch("client.client.Invoker.close") as close:
            self.assertEqual(main(["--check"]), 0)
        close.assert_called_once()

    def test_normal_eof_keyboard_and_network_error_close(self):
        for signal, expected in [(None, 0), (EOFError(), 0), (KeyboardInterrupt(), 130), (OSError("test"), 1)]:
            with self.subTest(signal=signal), patch("client.client.Invoker.close") as close, \
                    patch("client.client.run_menu", side_effect=signal):
                self.assertEqual(main([]), expected)
                close.assert_called_once()

    def test_invalid_arguments_and_mismatched_selector(self):
        for args in (["--port", "0"], ["--max-attempts", "0"], ["--case", "baseline"],
                     ["--case", "baseline", "--flight-id", "1001"],
                     ["--drop-first-request", f"{SESSION}:1"],
                     ["--case", "reply_loss_set", "--flight-id", "1001", "--new-price", "nan"]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as result:
                main(args)
            self.assertEqual(result.exception.code, 2)

    def test_log_file_is_parseable_actual_events(self):
        # 使用已被 Git 忽略的项目内缓存；兼容系统临时目录不可写的环境。
        cache = Path(__file__).resolve().parent / "__pycache__"
        cache.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache, suffix=".jsonl", delete=False) as stream:
            log_path = Path(stream.name)
        try:
            with patch("builtins.input", return_value="0"):
                self.assertEqual(main(["--session-id", str(SESSION), "--log-file", str(log_path)]), 0)
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events[0]["event"], "CLIENT_START")
            self.assertEqual(events[0]["sessionId"], str(SESSION))
        finally:
            log_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
