"""规范固定字节 + 非法报文；不能用生产编码器生成自己的期望值。"""

from dataclasses import replace
import json
import math
from pathlib import Path
import unittest

from client.input_validation import location, price
from client.models import (
    CallbackMessage, ErrorBody, FareResult, FlightQuery, Header, IncreaseAirfare,
    MonitorRegistration, Request, Reservation, RouteQuery, SetAirfare,
)
from client.protocol import MessageType, Operation, Semantics, Status
from client.protocol_codec import ProtocolError, decode_message, encode_request, to_binary32
from client.tests.helpers import SESSION, callback, detail, error, i32, monitor_reply, packet

VECTORS = {k: bytes.fromhex(v) for k, v in json.loads(
    Path(__file__).with_name("protocol_vectors.json").read_text(encoding="utf-8")).items()}


def request(op, body, size, request_id=1):
    return Request(Header(1, MessageType.REQUEST, op, SESSION, request_id,
                          Status.OK, Semantics.AMO, size), body)


class CodecTests(unittest.TestCase):
    def test_normative_request_vectors(self):
        self.assertEqual(encode_request(request(1, RouteQuery("SIN", "PEK"), 14)), VECTORS["ROUTE_REQUEST"])
        self.assertEqual(encode_request(request(4, MonitorRegistration(1001, 60), 8, 4)),
                         VECTORS["MONITOR_REQUEST"])

    def test_all_six_request_layouts(self):
        cases = [
            (1, RouteQuery("北京", "SIN"), "00000006e58c97e4baac0000000353494e"),
            (2, FlightQuery(1001), "000003e9"),
            (3, Reservation(1001, 2), "000003e900000002"),
            (4, MonitorRegistration(1001, 60), "000003e90000003c"),
            (5, SetAirfare(1001, 120), "000003e942f00000"),
            (6, IncreaseAirfare(1001, 20), "000003e941a00000"),
        ]
        for op, body, hex_body in cases:
            with self.subTest(op=op):
                raw = bytes.fromhex(hex_body)
                self.assertEqual(encode_request(request(op, body, len(raw))), packet(raw, kind=1, op=op))

    def test_normative_reply_vectors(self):
        route = decode_message(VECTORS["ROUTE_REPLY"])
        self.assertEqual(route.response.body.flightIds, (1001, 1002))
        details = decode_message(VECTORS["DETAIL_REPLY"]).response.body
        self.assertEqual((details.departure.year, details.departure.minute, details.airfare, details.availableSeats),
                         (2026, 30, 120.0, 10))
        self.assertEqual(decode_message(VECTORS["ERROR_REPLY"]).response.body, ErrorBody("Flight not found"))
        monitor = decode_message(VECTORS["MONITOR_REPLY"])
        self.assertEqual(monitor.response.body.remainingMillis, 59000)
        cb = decode_message(VECTORS["CALLBACK"])
        self.assertIsInstance(cb, CallbackMessage)
        self.assertEqual((cb.header.requestId, cb.flightId, cb.availableSeats, cb.updateSequence), (4, 1001, 8, 1))
        mode_error = decode_message(VECTORS["MODE_ERROR"])
        self.assertEqual(mode_error.header.semantics, Semantics.AMO)
        self.assertEqual(mode_error.response.status, Status.SEMANTICS_MISMATCH)

    def test_other_success_and_unknown_operation_error(self):
        self.assertEqual(decode_message(packet(i32(1001) + i32(8), op=3)).response.body.availableSeats, 8)
        for op in (5, 6):
            self.assertEqual(decode_message(packet(i32(1001) + bytes.fromhex("42f00000"), op=op)).response.body,
                             FareResult(1001, 120.0))
        self.assertEqual(decode_message(error(op=65535, status=6)).header.operation, 65535)

    def test_request_header_and_body_validation(self):
        good = request(2, FlightQuery(1001), 4)
        for changes in ({"version": 2}, {"messageType": MessageType.REPLY}, {"status": Status.INVALID_ARGUMENT},
                        {"bodyLength": 0}, {"requestId": 0}, {"requestId": 2**31},
                        {"semantics": 0}, {"clientSessionId": SESSION.__class__(int=0)}):
            with self.subTest(changes=changes), self.assertRaises(ProtocolError):
                encode_request(replace(good, header=replace(good.header, **changes)))
        for bad in (request(2, Reservation(1001, 2), 8), request(99, FlightQuery(1001), 4),
                    request(2, FlightQuery(2**31), 4), request(2, FlightQuery(True), 4)):
            with self.assertRaises(ProtocolError):
                encode_request(bad)
        # 负数量是表示有效的 i32，B 须返回业务错误，codec 不替代 B。
        self.assertEqual(encode_request(request(3, Reservation(1001, -1), 8))[-4:], b"\xff" * 4)

    def test_string_boundaries(self):
        self.assertEqual(encode_request(request(1, RouteQuery("", ""), 8))[-8:], b"\0" * 8)
        self.assertEqual(len(encode_request(request(1, RouteQuery("中"*42 + "ab", ""), 136))), 168)
        for source in ("中"*43, "\ud800"):
            with self.assertRaises(ProtocolError):
                encode_request(request(1, RouteQuery(source, "X"), 8))
        self.assertEqual(location("  北京  "), "北京")
        self.assertEqual(location("\t北京\t"), "\t北京\t")
        with self.assertRaises(ValueError):
            location("   ")

    def test_binary32_rounding_and_input_bounds(self):
        self.assertEqual(to_binary32(16777217.0), 16777216.0)
        for number in (float("nan"), float("inf"), -float("inf"), 1e40, True):
            with self.assertRaises(ProtocolError):
                to_binary32(number)
        with self.assertRaises(ProtocolError):
            price(1e-50, positive=True)
        self.assertEqual(math.copysign(1, price(-0.0)), 1)
        for number in (-1, 0):
            with self.assertRaises(ProtocolError):
                price(number, positive=True)

    def test_truncation_and_extra_tail(self):
        for name, raw in VECTORS.items():
            if name.endswith("REQUEST"):
                continue
            for length in range(len(raw)):
                with self.subTest(name=name, length=length), self.assertRaises(ProtocolError):
                    decode_message(raw[:length])
            with self.assertRaises(ProtocolError):
                decode_message(raw + b"\0")
            extended = raw[:28] + i32(len(raw) - 31) + raw[32:] + b"\0"
            with self.assertRaises(ProtocolError):
                decode_message(extended)

    def test_invalid_header_fields(self):
        raw = VECTORS["DETAIL_REPLY"]
        mutations = ((0, b"\2"), (1, b"\4"), (1, b"\1"), (4, bytes(16)), (20, i32(0)),
                     (20, i32(-1)), (24, b"\0\x0a"), (26, b"\0"), (27, b"\1"),
                     (28, i32(-1)), (28, i32(993)), (2, b"\xff\xff"))
        for offset, value in mutations:
            with self.subTest(offset=offset, value=value), self.assertRaises(ProtocolError):
                decode_message(raw[:offset] + value + raw[offset+len(value):])
        with self.assertRaises(ProtocolError):
            decode_message(bytes(1025))

    def test_bad_reply_bodies(self):
        bad = [
            packet(i32(0), op=1), packet(i32(101), op=1),
            packet(i32(2) + i32(1002) + i32(1001), op=1),
            packet(i32(2) + i32(1001) + i32(1001), op=1),
            packet(i32(1) + i32(-1), op=1),
            packet(i32(-1), status=2), packet(i32(0), status=2),
            packet(i32(257) + b"x"*257, status=2),
            packet(i32(1) + b"\xff", status=2),
            packet(i32(0) + i32(8), op=3),
            packet(i32(1001) + i32(-1), op=3),
            monitor_reply(-1), monitor_reply(3600001),
            callback(0), callback(-1), callback(flight=0), callback(seats=-1),
        ]
        date_body = detail()[32:]
        bad += [packet(date_body[:8] + i32(32) + date_body[12:]),
                packet(date_body[:12] + i32(24) + date_body[16:])]
        for bits in ("7fc00000", "7f800000", "bf800000", "80000000"):
            bad += [packet(date_body[:20] + bytes.fromhex(bits) + date_body[24:])]
        cb = callback()
        bad += [cb[:2] + b"\0\3" + cb[4:], cb[:24] + b"\0\2" + cb[26:]]
        for raw in bad:
            with self.subTest(raw=raw.hex()), self.assertRaises(ProtocolError):
                decode_message(raw)


if __name__ == "__main__":
    unittest.main()
