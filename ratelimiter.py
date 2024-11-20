import logging
import os
import sys
from datetime import datetime, timedelta
from concurrent import futures

import payment
import rates
from metrics import *
from utils import *

if bool(int(os.environ.get("REDIS_CLUSTER", False))):
    from redis.cluster import RedisCluster as Redis
else:
    from redis import Redis as Redis

import uuid

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(funcName)s: %(message)s",
    datefmt="[%Y-%m-%dT%H:%M:%S]",
)
logger = logging.getLogger(__name__)


def get_redis():
    c = Redis.from_url(
        f"redis://{os.environ.get('REDIS', 'localhost')}"
        + f":{int(os.environ.get('REDIS_SERVICE_PORT', 6379))}/0",
        decode_responses=True,
    )
    c.read_from_replicas = True
    return c


class Bucket(object):
    def __init__(self, name=None, redis=None):
        self.name = name
        self.store = redis

    def __get_name__(
        self, region, user, bucket, source, method, authority, now=None, prefix=""
    ):
        if now is None:
            now = datetime.now()
        return f"{prefix}" + str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{now.hour}|{now.minute}|{region}|{user}|{bucket}|{source}|{method}|{authority}",
            )
        )

    def show(
        self,
        region="",
        user="",
        bucket="",
        source="",
        method="",
        authority="",
        now=None,
        prefix="",
    ):
        bname = self.__get_name__(
            region, user, bucket, source, method, authority, now, prefix
        )
        try:
            return int(self.store.get(bname))
        except TypeError as rederr:
            logger.debug(rederr)
            return 0

    def inc(
        self,
        region="",
        user="",
        bucket="",
        source="",
        method="",
        authority="",
        now=None,
        prefix="",
    ):
        bname = self.__get_name__(
            region, user, bucket, source, method, authority, now, prefix
        )

        def increment(bname):
            try:
                r = self.store.incr(bname)
                try:
                    self.store.expire(bname, 1800)
                except Exception as rederr:
                    logger.error(f"cannot set expire on {bname} {rederr} {r}")
            except Exception as rederr:
                logger.error(f"redis error on incr {rederr}")

        with futures.ThreadPoolExecutor() as tpe:
            tpe.submit(increment, bname)

    def set(
        self,
        region="",
        user="",
        bucket="",
        source="",
        method="",
        authority="",
        now=None,
        prefix="",
        value=0,
    ):
        bname = self.__get_name__(
            region, user, bucket, source, method, authority, now, prefix
        )
        try:
            self.store.setex(bname, 60 * 60 * 24, value)
        except Exception as rederr:
            logger.error(f"redis error on incr {rederr}")


class RateBucket(object):
    def __init__(self, buckets=(1, 2, 5, 15, 30), redis=None):
        self.buckets = buckets
        self.store = redis

    @observe_redis_latency
    def show(self, region="", user="", bucket="", source="", method="", authority=""):
        try:
            return dict(
                zip(
                    self.buckets,
                    self.__show__(region, user, bucket, source, method, authority),
                )
            )
        except KeyError:
            return dict(zip(self.buckets, [0] * (len(self.buckets))))

    def __get_bucket__(self, region, user, bucket, source, method, authority, sbucket):
        now = datetime.now()
        return sum(
            map(
                lambda x: Bucket(redis=self.store).show(
                    region,
                    user,
                    bucket,
                    source,
                    method,
                    authority,
                    now - timedelta(minutes=x),
                ),
                range(sbucket),
            )
        )

    def __show__(self, region, user, bucket, source, method, authority):
        try:
            for sbucket in self.buckets:
                yield int(
                    self.__get_bucket__(
                        region, user, bucket, source, method, authority, sbucket
                    )
                )
        except TypeError:
            yield 0

    @observe_redis_latency
    def inc(self, region, user, bucket, source, method, authority):
        try:
            Bucket(redis=self.store).inc(
                region, user, bucket, source, method, authority
            )
        except Exception as storerr:
            logger.debug(f"RateBucket: {storerr}")


class PaymentBucket(object):
    def __init__(self, buckets=(1, 2, 12, 24), redis=None):
        self.buckets = buckets
        self.store = redis

    def show(
        self,
        region="",
        user="",
        bucket="",
        source="",
        method="",
        authority="",
        prefix="pay",
    ):
        try:
            return dict(
                zip(
                    self.buckets,
                    self.__show__(region, user, bucket, source, method, authority),
                )
            )
        except KeyError:
            return dict(zip(self.buckets, [0] * (len(self.buckets))))

    def __get_bucket__(
        self, region, user, bucket, source, method, authority, sbucket, prefix="pay"
    ):
        now = datetime.now()
        return sum(
            map(
                lambda x: Bucket(redis=self.store).show(
                    region,
                    user,
                    bucket,
                    source,
                    method,
                    authority,
                    (now - timedelta(hours=x)).replace(minute=0),
                    prefix,
                ),
                range(sbucket),
            )
        )

    def __show__(self, region, user, bucket, source, method, authority, prefix="pay"):
        try:
            for sbucket in self.buckets:
                yield int(
                    self.__get_bucket__(
                        region, user, bucket, source, method, authority, sbucket
                    )
                )
        except TypeError:
            yield 0

    def set(
        self,
        region,
        user,
        bucket,
        source,
        method,
        authority,
        now=None,
        prefix="pay",
        value=0,
    ):
        try:
            Bucket(redis=self.store).set(
                region, user, bucket, source, method, authority, now, prefix, value
            )
        except Exception as storerr:
            logger.debug(f"RateBucket: {storerr}")


def rateon(auth):
    logger.debug(f"rateon: {auth}")
    return (
        dict(
            region=auth.get("region", "us-east-1"),
            user="",
            bucket="",
            source="",
            method="",
            authority="",
        ),
        dict(
            region=auth.get("region", "us-east-1"),
            user=auth.get("user", "anonymous"),
            bucket="",
            source="",
            method="",
            authority="",
        ),
        dict(
            region=auth.get("region", "us-east-1"),
            user=auth.get("user", "anonymous"),
            bucket=auth.get("bucket"),
            source="",
            method="",
            authority="",
        ),
        dict(
            region=auth.get("region", "us-east-1"),
            user=auth.get("user", "anonymous"),
            bucket=auth.get("bucket"),
            source=auth.get("source"),
            method="",
            authority="",
        ),
        dict(
            region=auth.get("region", "us-east-1"),
            user=auth.get("user", "anonymous"),
            bucket=auth.get("bucket"),
            source=auth.get("source"),
            method=auth.get("method"),
            authority=auth.get("authority"),
        ),
        dict(
            region="",
            user=auth.get("user", "anonymous"),
            bucket="",
            source="",
            method="",
            authority="",
        ),
        dict(
            region="",
            user=auth.get("user", "anonymous"),
            bucket=auth.get("bucket"),
            source="",
            method="",
            authority="",
        ),
        dict(
            region="",
            user=auth.get("user", "anonymous"),
            bucket=auth.get("bucket"),
            source=auth.get("source"),
            method=auth.get("method"),
            authority="",
        ),
    )


def payon(auth):
    logger.debug(f"payon: {auth}")
    return (
        dict(
            region="",
            user=auth.get("user", "anonymous"),
            bucket=auth.get("bucket"),
            source="",
            method="",
            authority="",
        ),
        dict(
            region="",
            user=auth.get("user", "anonymous"),
            bucket=auth.get("bucket"),
            source="",
            method=auth.get("method"),
            authority="",
        ),
    )


@observe_latency
def ratelimit(req):
    try:
        req = parse_requests_data(req)
        S3_REQUEST.labels(
            req.get("user"),
            req.get("bucket"),
            req.get("method"),
            req.get("source"),
            req.get("region"),
            req.get("authority"),
        ).inc()
        if req.get("method") in ("GET", "POST", "PUT"):
            S3_REQUEST_SIZE.labels(
                req.get("user"),
                req.get("bucket"),
                req.get("method"),
                req.get("source"),
                req.get("region"),
                req.get("authority"),
            ).inc(req.get("length"))
        del req["length"]
    except Exception as err:
        logger.error(f"cannot parse OpenPolicyAgent request {err}")
        return 500, None, []

    try:
        Rater = RateBucket(buckets=(1,), redis=get_redis())
        list(map(lambda x: Rater.inc(**x), rateon(req)))
        buckets = list(map(lambda x: (x, Rater.show(**x)), rateon(req)))
        for check in filter(lambda x: x.startswith("rate_check_"), dir(rates)):
            if not getattr(rates, check)(buckets, req):
                S3_RATELIMITED.labels(
                    req.get("user"),
                    req.get("bucket"),
                    req.get("method"),
                    req.get("source"),
                    req.get("region"),
                    req.get("authority"),
                ).inc()
                return 429, None, [("x-rate-limited", str(buckets))]
        return 200, None, []

    except Exception as err:
        logger.error(f"ratelimit: {err}")
        logger.debug(f"ratelimit: {req}")
        return 500, None, []
    return 200, None, []


@observe_latency
def paymentcheck(req):
    try:
        req = parse_requests_data(req)
        S3_REQUEST.labels(
            req.get("user"),
            req.get("bucket"),
            req.get("method"),
            req.get("source"),
            req.get("region"),
            req.get("authority"),
        ).inc()
    except Exception as err:
        logger.error(f"cannot parse OpenPolicyAgent request {err}")
        return 500, None, []
    try:
        # ensure user is not None
        if req.get("user") is None:
            req["user"] = "anonymous"
    except Exception as sanerr:
        logger.error(
            f"Sanity on req.get('user') {req.get('user')} failed with {sanerr}"
        )
    try:
        Payment = PaymentBucket(redis=get_redis())
        buckets = list(map(lambda x: (x, Payment.show(**x)), payon(req)))
        for check in filter(lambda x: x.startswith("pay_check_"), dir(payment)):
            if not getattr(payment, check)(buckets, req):
                S3_RATELIMITED.labels(
                    req.get("user"),
                    req.get("bucket"),
                    req.get("method"),
                    req.get("source"),
                    req.get("region"),
                    req.get("authority"),
                ).inc()
                return 402, None, [("x-payment-required", str(buckets))]

        return 200, None, []

    except Exception as err:
        logger.error(f"{err}")
        logger.debug(f"{req}")
        return 500, None, []
    return 200, None, []
