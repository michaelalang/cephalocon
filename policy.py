import datetime
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(funcName)s: %(message)s",
    datefmt="[%Y-%m-%dT%H:%M:%S]",
)
logger = logging.getLogger(__name__)
# buckets is an array of tuples where item[0] is counter matches
#                                     item[1] is the counter values
# [ (dict
# define bucket name to values
min1, min2, min5, min15, min30 = 1, 2, 5, 15, 30
br, bv = 0, 1

redirect308 = """<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>PermanentRedirect</Code><Message>The bucket you are attempting to access must be addressed using the specified endpoint. Please send all future requests to this endpoint.</Message><RequestId>%s</RequestId><Endpoint>%s</Endpoint><HostId>%s</HostId></Error>
"""

timerestriction = """<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>PreconditionFailed</Code><Message>The bucket s not accessible due to time restrictions.</Message><RequestId>%s</RequestId><Endpoint>%s</Endpoint><HostId>%s</HostId></Error>
"""

endpoints = {
    "s3.example.com": "s3-east.example.com",
    "s3-east.example.com": "s3-west.example.com",
    "s3-west.example.com": "s3-east.example.com",
}
regions = {
    "us-east-1": "s3-east.example.com",
    "us-west-1": "s3-west.example.com",
}


def policy_check_region_redirect(req, jrq):
    if not bool(int(os.environ.get("REGION_REDIRECT", 0))):
        return (200, "", [])
    logger.info(f"check redirect {req.get('authority')} {req.get('region')}")
    if all(
        [
            req.get("authority") in ("s3-east.example.com"),
            req.get("region") == "us-west-1",
        ]
    ):
        return (
            308,
            redirect308
            % (
                req.get("x-request-id"),
                endpoints[req.get("authority")],
                req.get("authority"),
            ),
            [
                (
                    "Location",
                    f"{jrq['attributes']['request']['http']['scheme']}://"
                    + f"{regions[req.get('region')]}/{jrq['attributes']['request']['http']['headers'][':path']}",
                )
            ],
        )
    elif all(
        [
            req.get("authority") in ("s3-west.example.com"),
            req.get("region") == "us-east-1",
        ]
    ):
        return (
            308,
            redirect308
            % (
                req.get("x-request-id"),
                endpoints[req.get("authority")],
                req.get("authority"),
            ),
            [
                (
                    "Location",
                    f"{jrq['attributes']['request']['http']['scheme']}://"
                    + f"{regions[req.get('region')]}/{jrq['attributes']['request']['http']['headers'][':path']}",
                )
            ],
        )
    elif all(
        [
            req.get("authority") in ("s3-east.example.com"),
            req.get("region") == "us-west-1",
        ]
    ):
        return (
            308,
            redirect308
            % (
                req.get("x-request-id"),
                endpoints[req.get("authority")],
                req.get("authority"),
            ),
            [
                (
                    "Location",
                    f"{jrq['attributes']['request']['http']['scheme']}://"
                    + f"{regions[req.get('region')]}/{jrq['attributes']['request']['http']['headers'][':path']}",
                )
            ],
        )
    return (200, "", [])


def disable_policy_check_timebase(req, jrq):
    logger.debug(
        f"check time {datetime.datetime.now().minute} % 3 {datetime.datetime.now().minute % 3 == 0}"
    )
    if datetime.datetime.now().minute % 3 == 0:
        return (
            412,
            timerestriction
            % (
                req.get("x-request-id"),
                req.get("authority"),
                req.get("authority"),
            ),
            [],
        )
    return (200, "", [])
