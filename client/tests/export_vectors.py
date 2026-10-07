"""生成交给 A 的六个实际 Python 请求向量：python -m client.tests.export_vectors。"""

from dataclasses import asdict
import json

from client.models import (FlightQuery, Header, IncreaseAirfare, MonitorRegistration,
                           Request, Reservation, RouteQuery, SetAirfare)
from client.protocol import MessageType, Operation, Semantics, Status, VERSION
from client.protocol_codec import encode_request, request_body_length
from client.tests.helpers import SESSION


def main() -> None:
    bodies = (RouteQuery("SIN", "PEK"), FlightQuery(1001), Reservation(1001, 2),
              MonitorRegistration(1001, 60), SetAirfare(1001, 120.0), IncreaseAirfare(1001, 20.0))
    vectors = []
    for operation, body in zip(Operation, bodies):
        header = Header(VERSION, MessageType.REQUEST, operation, SESSION, int(operation),
                        Status.OK, Semantics.AMO, request_body_length(operation, body))
        raw = encode_request(Request(header, body))
        vectors.append({"operation": operation.name, "requestId": header.requestId,
                        "body": asdict(body), "bytes": len(raw), "hex": raw.hex()})
    print(json.dumps({"source": "Python client encoder; not a Java interoperability result",
                      "sessionId": str(SESSION), "semantics": "AMO", "vectors": vectors},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
