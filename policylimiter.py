import logging
import os
import sys

import policy
from metrics import *
from utils import *

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(funcName)s: %(message)s",
    datefmt="[%Y-%m-%dT%H:%M:%S]",
)
logger = logging.getLogger(__name__)


@observe_latency
def policylimit(jrq):
    try:
        req = parse_requests_data(jrq)
        req["x-request-id"] = (
            jrq.get("attributes")
            .get("request")
            .get("http")
            .get("headers")
            .get("x-request-id")
        )
    except Exception as err:
        logger.error(f"cannot parse OpenPolicyAgent request {err}")
        return 500, None, []

    try:
        body = None
        headers = []
        for check in filter(lambda x: x.startswith("policy_check_"), dir(policy)):
            check, body, headers = getattr(policy, check)(req)
            if not check == 200:
                S3_POLICYLIMITED.labels(
                    req.get("user"),
                    req.get("bucket"),
                    req.get("method"),
                    req.get("source"),
                    req.get("region"),
                    req.get("authority"),
                ).inc()
                return check, body, headers
        return check, body, headers

    except Exception as err:
        logger.error(f"{err}")
        return 500, None, []
    return 200, None, []
