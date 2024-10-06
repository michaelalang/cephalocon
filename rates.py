import logging
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


def rate_check_limit_fast(buckets, req):
    if not all(
        [
            req.get("authority") == "s3.example.com",
        ]
    ):
        return True
    for bucket in buckets:
        if not all(
            [
                bucket[br].get("bucket") in ("*", req.get("bucket")),
            ]
        ):
            continue
        if not all(
            [
                req.get("bucket") in ("*", "user1"),
                req.get("user") == "user1",
            ]
        ):
            continue
        if bucket[bv][min1] > 3:
            logger.error(
                f"[REJECT] check {req.get('authority')} bucket {req.get('bucket')}"
                + f" user {req.get('user')} req-count {bucket[1][min1]} bv {bucket[bv]}"
            )
            return False
    return True
