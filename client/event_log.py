"""[C-08] JSON Lines 仅用于本地证据日志；UDP 协议始终是手工二进制。"""

import json
import logging
import time

LOGGER = logging.getLogger("sc6103.client")


def record(event: str, **fields: object) -> None:
    LOGGER.info(json.dumps({"event": event, "monotonic": time.monotonic(), **fields},
                           ensure_ascii=False, default=str, allow_nan=False))
