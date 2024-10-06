#!/usr/bin/python3

import json
import logging
import os
import sys
import time
import urllib.parse
from concurrent import futures
from datetime import datetime, timedelta

import envoy.service.auth.v3.external_auth_pb2 as pb2
import envoy.service.auth.v3.external_auth_pb2_grpc as pb2_grpc
import grpc
import requests
import urllib3.exceptions
from envoy.type.v3 import http_status_pb2 as _http_status_pb2
from flask import Flask, Response, abort, jsonify, make_response, request
from google.protobuf.json_format import MessageToJson
from google.rpc import status_pb2 as _grpc_status_pb2

import policylimiter
import ratelimiter
from metrics import *

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(funcName)s: %(message)s",
    datefmt="[%Y-%m-%dT%H:%M:%S]",
)
logger = logging.getLogger(__name__)


class AuthorizationServer(pb2_grpc.AuthorizationServicer):

    def __init__(self, *args, **kwargs):
        pass

    def response(self, check=200, body="", jrq=None):
        if check == 200:
            GRPC_REQUESTS_TOTAL.labels(check).inc()
            accept = pb2.OkHttpResponse()
            rsp = pb2.CheckResponse(ok_response=accept)
            logger.info(
                f"[ACCEPT] {str(jrq.get('attributes').get('request').get('http').get('headers'))}"
            )
            return accept
        elif check == 402:
            GRPC_REQUESTS_TOTAL.labels(check).inc()
            reject = pb2.DeniedHttpResponse(
                status=_http_status_pb2.HttpStatus(
                    code=_http_status_pb2.PaymentRequired
                )
            )
            rsp = pb2.CheckResponse(
                status=_grpc_status_pb2.Status(code=1), denied_response=reject
            )
            logger.info(f"[REJECT]({check}) {str(jrq)}")
            return rsp
        elif check == 428:
            GRPC_REQUESTS_TOTAL.labels(check).inc()
            reject = pb2.DeniedHttpResponse(
                status=_http_status_pb2.HttpStatus(
                    code=_http_status_pb2.PreconditionRequired
                )
            )
            rsp = pb2.CheckResponse(
                status=_grpc_status_pb2.Status(code=1), denied_response=reject
            )
            logger.info(f"[REJECT]({check}) {str(jrq)}")
            return rsp
        elif check == 429:
            GRPC_REQUESTS_TOTAL.labels(check).inc()
            reject = pb2.DeniedHttpResponse(
                status=_http_status_pb2.HttpStatus(
                    code=_http_status_pb2.TooManyRequests
                )
            )
            rsp = pb2.CheckResponse(
                status=_grpc_status_pb2.Status(code=1), denied_response=reject
            )
            logger.info(f"[REJECT]({check}) {str(jrq)}")
            return rsp
        elif check == 308:
            GRPC_REQUESTS_TOTAL.labels(check).inc()
            redirect = pb2.DeniedHttpResponse(
                status=_http_status_pb2.HttpStatus(
                    code=_http_status_pb2.PermanentRedirect,
                ),
                body=body,
            )
            rsp = pb2.CheckResponse(
                status=_grpc_status_pb2.Status(code=1),
                denied_response=redirect,
            )
            logger.info(f"[REDIRECT]({check}) {str(jrq)}")
            return rsp
        elif check == 412:
            GRPC_REQUESTS_TOTAL.labels(check).inc()
            redirect = pb2.DeniedHttpResponse(
                status=_http_status_pb2.HttpStatus(
                    code=_http_status_pb2.PreconditionFailed,
                ),
                body=body,
            )
            rsp = pb2.CheckResponse(
                status=_grpc_status_pb2.Status(code=1),
                denied_response=redirect,
            )
            logger.info(f"[PRECONDITION]({check}) {str(jrq)}")
            return rsp
        else:
            GRPC_REQUESTS_TOTAL.labels(check).inc()
            reject = pb2.DeniedHttpResponse(
                status=_http_status_pb2.HttpStatus(
                    code=_http_status_pb2.InternalServerError
                )
            )
            rsp = pb2.CheckResponse(
                status=_grpc_status_pb2.Status(code=1), denied_response=reject
            )
            logger.info(f"[REJECT]({check}) {str(jrq)}")
            return rsp

    def Check(self, request, context):

        jrq = json.loads(MessageToJson(request))
        body = ""
        checks = []
        with futures.ThreadPoolExecutor(max_workers=3) as tpe:
            checks.append(tpe.submit(policylimiter.policylimit, jrq))
            checks.append(tpe.submit(ratelimiter.ratelimit, jrq))
            checks.append(tpe.submit(ratelimiter.paymentcheck, jrq))
            futures.wait(checks)

        for check, body in map(lambda x: x.result(), checks):
            if not check == 200:
                return self.response(check, body, jrq)

        return self.response(200, "", jrq)


def serve():
    try:
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=int(os.environ.get("THREADS", 10))),
            interceptors=[],
        )
        pb2_grpc.add_AuthorizationServicer_to_server(AuthorizationServer(), server)
        server.add_insecure_port(f'[::]:{os.environ.get("GRPCPORT", 50051)}')
        server.start()
        server.wait_for_termination()
    except Exception as e:
        logger.error(f"GRPC exception {e}")
        sys.exit(0)


app = Flask(__name__)


def serve_flask():
    tpe = futures.ThreadPoolExecutor(max_workers=int(os.environ.get("THREADS", 10)))
    tpe.submit(
        app.run,
        **{
            "host": os.environ.get("LISTEN", "0.0.0.0"),
            "port": int(os.environ.get("PORT", 8080)),
            "threaded": True,
        },
    )


def payment_sync():
    def fetchall_prom_values():
        for hour in Payment.buckets:
            q = (
                'sum by (user, bucket) (count_over_time(s3_request_size_total{authority=~".*", region=~".*"}['
                + str(hour)
                + "h]))"
            )
            try:
                req = requests.get(
                    f"{PROMQLAPI}/query?{urllib.parse.urlencode(dict(query=q))}"
                )
                data = req.json()
            except:
                continue
            for metric in data["data"]["result"]:
                Payment.set(
                    user=metric["metric"].get("user", ""),
                    bucket=metric["metric"].get("bucket", ""),
                    region="",
                    source="",
                    method="",
                    authority="",
                    value=int(metric["value"][-1]),
                    now=now.replace(hour=hour - 1, minute=0),
                )

    while True:
        starttime = time.time()
        try:
            PROMQLAPI = os.environ.get("PROMQLAPI", "http://localhost:9090/api/v1")
            now = datetime.now()
            Payment = ratelimiter.PaymentBucket(redis=ratelimiter.get_redis())
            logger.info(f"updating Payment from {PROMQLAPI}")
            fetchall_prom_values()
        except Exception as payerr:
            logger.error(f"PaymentSync {payerr}")
        stoptime = time.time()
        logger.info(f"finished in {timedelta(seconds=stoptime-starttime)}")
        time.sleep(int(os.environ.get("PROM_REFRESH", 300)))


@app.route("/metrics", methods=["GET"])
def generate_metrics():
    return Response(
        response=generate_latest(registry),
        status=200,
    )


@app.route("/health", methods=["GET"])
def health():
    # very simple check to see if GRPC is up
    try:
        requests.get(f'http://localhost:{os.environ.get("PORT", 50051)}')
    except requests.exceptions.ConnectionError:
        return jsonify(dict(status="ok")), 200
    except urllib3.exceptions.MaxRetryError:
        return jsonify(dict(status="error")), 503


if __name__ == "ext_auth_grpc_server":
    # start GRPC when running with gunicorn
    tpe = futures.ThreadPoolExecutor(max_workers=int(os.environ.get("THREADS", 10)))
    tpe.submit(serve)

    # start payment updates from prometheus
    tpe = futures.ThreadPoolExecutor(max_workers=int(os.environ.get("THREADS", 10)))
    tpe.submit(payment_sync)

if __name__ == "__main__":
    serve_flask()
    serve()
