# payment specific content
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

h1, h2, h12, h24 = 1, 2, 12, 24
br, bv = 0, 1


def pay_check_limit_fast(buckets, req):
    for bucket in buckets:
        if not all(
            [
                req.get("bucket") in ("*", "user2"),
                req.get("user") == "user2",
            ]
        ):
            continue
        if bucket[bv][h24] > 500:
            logger.info(
                f"[REJECT] check {req.get('authority')} bucket {req.get('bucket')}"
                + f" user {req.get('user')} req-count {bucket[1][h24]} bv {bucket[bv]}"
            )
            return False
    return True
