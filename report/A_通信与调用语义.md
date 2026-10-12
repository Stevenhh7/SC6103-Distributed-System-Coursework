# Part A: Protocol, UDP and Invocation Semantics

Author: Zhang Zhiyin. Completed 10 October 2026. This chapter accompanies the integrated English report in 项目报告.md.

## Implementation

BinaryProtocolCodec implements all seven codec entry points against protocol v1.0. It uses explicit big-endian byte shifts for numbers and UUIDs, binary32 bit conversion, strict UTF-8 and exact-length readers. It validates the 32-byte header, maximum 1024-byte application packet and the shapes of every request, reply and callback. Untrustworthy identities are dropped; trustworthy malformed requests receive bounded protocol errors. Business-invalid typed values remain the responsibility of B's service.

UdpTransport owns one IPv4 DatagramSocket with a 65535-byte receive buffer and 250 ms timeout. It preserves only the actual received bytes and endpoint. UdpServer loads the shared seed, purges subscriptions and dispatches sequentially. Closing the server unblocks reception and supports a clean shutdown. There is no stream marshalling or per-request worker thread.

RequestDispatcher enforces mode validation before duplicate handling. AMO history is keyed by session UUID and request ID, retaining immutable original bytes, source peer and result. Matching duplicates replay; conflicting bytes or endpoints are rejected. Successful business results and business errors are cached before reply loss/send. ALO executes each delivery. InMemoryRequestHistory prevents accidental replacement and exposes defensive snapshots.

LossSimulator drops exactly the first ordinary reply for the configured request key. It never drops callbacks implicitly. Reply-send failure is isolated from callback processing; callbacks are individually checked for active subscriptions and sent from the same server socket. AMO replay does not invoke business logic or regenerate events. Monitor confirmations refresh only the original registration's remaining lifetime immediately before sending, returning zero for an expired/replaced registration without renewal.

ServerLog outputs JSON Lines for actual request receipt, execution, history insertion, cache hits, dropped replies and callback/reply sends or failures. UUID/requestId and raw bytes make experiment assertions traceable. Package-private sender and clock injection enable deterministic failure/expiry tests without changing the wire protocol or public constructor.

## Integration and evidence

Part A adds 19 protocol groups and 21 semantic/transport groups, 12 real Java/Python integration tests, 3 monitor-analysis regressions and 6 server-audit regressions. Existing B's 49 and C's 63 tests plus 27 original experiment-tool tests also pass: 200 total. Sixteen real UDP experiments separately cover eight cases in each mode. The final runtime was Java 17; exact tested source hashes and original outputs are in evidence/a/release-java17/.

First lost reservation reply: ALO executes twice and leaves 8 seats; AMO executes once, replays once and leaves 9. First lost increase reply: ALO reaches 140, AMO 120. SET reaches 120 in both modes, but the execution audit proves two versus one execution. All-request loss leaves 10 seats in either mode; all-reply loss leaves 5 in ALO and 9 in AMO, although both clients report unknown after five attempts.

The complete result table, architecture, protocol and monitoring analysis are in sections 1-7 of the integrated report. Dual-monitor, flight isolation, original registration identity, expired/replaced confirmation replay and callback-before-confirmation paths have real-network coverage. Injected I/O failures additionally verify that a failed reply or recipient does not suppress other callbacks.

## Scope boundaries

The protocol and existing B/C business/client APIs remain unchanged. The targeted shared-tool fix rejects premature MONITOR_END evidence instead of accepting an incomplete monitoring run. Historical evidence is retained and labelled separately.

AMO applies only while this server process retains history; it is not exactly-once or persistent recovery. Callback delivery is best effort. Three physical computers were unavailable for this run, so the three-machine demonstration remains an explicit team action. Actual contribution percentages must be agreed by the three named members before submission.
