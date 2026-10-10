"""审查用复现：模拟日志只验证核对器边界，不是 Java/Python 联调证据。

从仓库根目录执行：python -X utf8 evidence/c/2026-10-08-bc-review-repro.py
不修改 A/B/C 源码；中间文件保留在 work/__pycache__/bc-review-evidence。
"""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.analyze_results import EvidenceError, analyze, load_events, main
from experiments.test_analyze_results import client_evidence
from client.tests.helpers import SESSION


def main_review():
    folder = ROOT / "work" / "__pycache__" / "bc-review-evidence"
    # 普通项目目录，避开当前受限环境中 TemporaryDirectory 的权限问题。
    folder.mkdir(parents=True, exist_ok=True)
    records = []

    for mode in ("alo", "amo"):
        original, exit_code, proxy = client_evidence("monitor", mode)
        original_result = analyze(original, "monitor", mode, SESSION, exit_code, proxy)
        changed = deepcopy(original)
        start = next(e for e in changed if e["event"] == "MONITOR_START")
        end_index = next(i for i, e in enumerate(changed) if e["event"] == "MONITOR_END")
        end = changed[end_index]
        wait = end["monotonic"] - start["monotonic"]
        for event in changed[end_index:]:
            if "monotonic" in event:
                event["monotonic"] -= wait
        # 2026-10-10: R2 is fixed; retain the historical probe as a regression.
        try:
            analyze(changed, "monitor", mode, SESSION, exit_code, proxy)
        except EvidenceError:
            result = {"result": "EARLY_MONITOR_REJECTED"}
        else:
            raise AssertionError("Early monitor termination was accepted")
        assert end["monotonic"] < start["deadline"]
        log = folder / f"synthetic-early-monitor-{mode}.jsonl"
        log.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in changed) + "\n",
                       encoding="utf-8")
        records.append(dict(
            check="synthetic_monitor_ends_before_deadline_is_rejected", mode=mode,
            baseline_result=original_result["result"], result=result["result"],
            confirmation_remaining_ms=next(e["body"]["remainingMillis"] for e in changed
                                           if e["event"] == "REPLY" and e["requestId"] == 2),
            start=start["monotonic"], deadline=start["deadline"], end=end["monotonic"],
            evidence_kind="synthetic log regression probe; NOT network integration"))

    # 与受权限影响的测试核对同一 CLI 行为；不把此探测冒充原测试通过。
    malformed, output = folder / "malformed-client.jsonl", folder / "failure-analysis.json"
    malformed.write_text('{"event":', encoding="utf-8")
    with redirect_stdout(io.StringIO()):
        code = main(["--client-log", str(malformed), "--case", "baseline", "--mode", "amo",
                     "--session", str(SESSION), "--client-exit", "0", "--output", str(output)])
    analysis = json.loads(output.read_text(encoding="utf-8"))
    assert code == 1 and analysis["result"] == "FAILED_OR_INCOMPLETE"
    try:
        load_events(malformed)
    except EvidenceError:
        rejected = True
    else:
        raise AssertionError("Malformed JSONL was accepted")
    records.append(dict(check="incomplete_log_cli_in_plain_workspace_directory", passed=True,
                        exit_code=code, result=analysis["result"], loader_rejected=rejected,
                        evidence_kind="equivalent assertions; this probe alone does not rerun the original unittest"))
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main_review()
