import logging
import sys
from functools import wraps
from time import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Enum,
    Gauge,
    Histogram,
    Info,
    Summary,
    multiprocess,
)
from prometheus_client.openmetrics.exposition import generate_latest

from utils import parse_requests_data

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)

registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)


def observe_latency(func):
    @wraps(func)
    def metrics_wrapped(*args, **kwargs):
        starttime = time()
        rsp = func(*args, **kwargs)
        stoptime = time()
        name = func.__name__
        data = parse_requests_data(args[0])
        S3_REQUEST_LATENCY.labels(
            name, data["method"], data["authority"], data["bucket"]
        ).observe(
            stoptime - starttime,
        )
        return rsp

    return metrics_wrapped


def observe_redis_latency(func):
    @wraps(func)
    def metrics_wrapped(*args, **kwargs):
        starttime = time()
        rsp = func(*args, **kwargs)
        stoptime = time()
        name = func.__name__
        REDIS_REQUEST_LATENCY.labels(name).observe(
            stoptime - starttime,
        )
        return rsp

    return metrics_wrapped


GRPC_REQUESTS_TOTAL = Counter(
    "grpc_requests_total", "Total requests recieved", ["code"]
)

S3_REQUEST = Counter(
    "s3_request",
    "S3 Protocol request",
    ["user", "bucket", "method", "source", "region", "authority"],
)

S3_RATELIMITED = Counter(
    "s3_rate_limited",
    "S3 total rate limited requests",
    ["user", "bucket", "method", "source", "region", "authority"],
)

S3_REQUEST_SIZE = Counter(
    "s3_request_size",
    "S3 Protocol requests sizes for PUT|POST|GET",
    ["user", "bucket", "method", "source", "region", "authority"],
)

S3_PAYMENT = Counter(
    "s3_payment_required",
    "S3 total payment required users",
    ["user", "bucket", "method", "source", "region", "authority"],
)

S3_POLICYLIMITED = Counter(
    "s3_policy_limited",
    "S3 total policy limited requests",
    ["user", "bucket", "method", "source", "region", "authority"],
)

S3_REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "Requests latency in seconds",
    ["name", "method", "authority", "bucket"],
)

REDIS_REQUEST_LATENCY = Histogram(
    "redis_request_latency_seconds", "Redis Requests latency in seconds", ["name"]
)
