#!/usr/bin/python3.13t
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, wait
from time import sleep, time

import boto3
from botocore.client import Config
from faker import Faker

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


def config(region):
    return Config(
        connect_timeout=int(os.environ.get("BOTO3_TIMEOUT", 5)),
        read_timeout=int(os.environ.get("BOTO3_TIMEOUT", 30)),
        signature_version="s3v4",
        region_name=f"us-{region}-1",
    )


faker = Faker()


def region_to_endpoint(region):
    return "https://s3.example.com"


def update(access_key, secret_key, region):
    fkey = faker.uuid4()
    if True:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=region_to_endpoint(region),
            config=config(region),
        )
    for _ in range(faker.random_number(digits=2)):
        logger.info(f"[{access_key}/us-{region}-1](DELETE): {fkey}")
        try:
            s3.delete_object(
                Bucket=access_key,
                Key=fkey,
            )
        except:
            # initial delete might fail
            pass
        logger.info(f"[{access_key}/us-{region}-1](PUT): {fkey}")
        try:
            s3.put_object(
                Bucket=access_key,
                Key=fkey,
                Expires=int(time() + 600),
                ACL="private",
                Body=region.encode("utf8"),
            )
            if not bool(int(os.environ.get("NOSLEEP", 0))):
                sleep(faker.random.random())
        except Exception as puterr:
            logger.error(f"[{access_key}/us-{region}-1](PUT): Exception {puterr}")


def remove(access_key, secret_key, region):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=region_to_endpoint(region),
            config=config(region),
        )
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=access_key)
        for objects in pages:
            for obj in faker.random_choices(objects.get("Contents", []), 5):
                logger.info(f"[{access_key}/us-{region}-1](DELETE): {obj.get('Key')}")
                s3.delete_object(Bucket=access_key, Key=obj.get("Key"))
    except Exception as s3err:
        logger.error(f"[{access_key}/us-{region}-1](DELETE): Exception {s3err}")
        return


def adder(access_key, secret_key, region):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=region_to_endpoint(region),
            config=config(region),
        )
        for n in range(faker.random_number(digits=2)):
            try:
                fkey = faker.uuid4()
                logger.info(f"[{access_key}/us-{region}-1](PUT): {fkey}")
                s3.put_object(
                    Bucket=access_key,
                    Key=fkey,
                    Expires=int(time() + 600),
                    ACL="private",
                    Body="\n".join(faker.sentences(25)).encode("utf8"),
                )
            except Exception as s3err:
                logger.error(
                    f"[{access_key}/us-{region}-1](PUT): {fkey} Exception {s3err}"
                )
                return
            if not bool(int(os.environ.get("NOSLEEP", 0))):
                sleep(faker.random.random())
    except Exception as s3err:
        logger.error(f"[{access_key}/us-{region}-1](PUT): Exception {s3err}")
        return


def getters(access_key, secret_key, region):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=region_to_endpoint(region),
            config=config(region),
        )
        for n in range(faker.random_number(digits=2)):
            try:
                paginator = s3.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=access_key)
                for objects in pages:
                    for obj in objects.get("Contents", []):
                        logger.info(
                            f"[{access_key}/us-{region}-1](HEAD): {obj.get('Key')}"
                        )
                        try:
                            s3.head_object(Bucket=access_key, Key=obj.get("Key"))
                        except Exception as s3err:
                            logger.error(
                                f"[{access_key}/us-{region}-1](HEAD): {obj.get('Key')} Exception {s3err}"
                            )
                        if faker.random_choices(
                            [True, False, True, True, True, False], 1
                        )[0]:
                            logger.info(
                                f"[{access_key}/us-{region}-1](GET): {obj.get('Key')}"
                            )
                            try:
                                s3.get_object(Bucket=access_key, Key=obj.get("Key"))
                            except Exception as s3err:
                                logger.error(
                                    f"[{access_key}/us-{region}-1](GET): {obj.get('Key')} Exception {s3err}"
                                )
            except Exception as s3err:
                logger.error(f"[{access_key}/us-{region}-1](GET): Exception {s3err}")
            if not bool(int(os.environ.get("NOSLEEP", 0))):
                sleep(faker.random.random())
    except Exception as s3err:
        logger.error(f"[{access_key}/us-{region}-1](GET): Exception {s3err}")
        return


def writers():
    writers = []
    while True:
        logger.info(f"[WRITERS]: Rotating Users/Buckets")
        with ThreadPoolExecutor(max_workers=int(os.environ.get("THREADS", 2))) as tpe:
            for _ in range(2):
                region = faker.random_choices(["east", "west"], 1)[0]
                access_key = f"user{faker.random_choices(range(1, 50), 1)[0]}"
                secret_key = access_key
                writers.append(tpe.submit(adder, access_key, secret_key, region))
        wait(writers)


def readers():
    readers = []
    while True:
        logger.info(f"[READERS]: Rotating Users/Buckets")
        with ThreadPoolExecutor(max_workers=int(os.environ.get("THREADS", 10))) as tpe:
            for _ in range(int(os.environ.get("THREADS", 10 - 1))):
                access_key = f"user{faker.random_choices(range(1, 50), 1)[0]}"
                secret_key = access_key
                region = faker.random_choices(["east", "west"], 1)[0]
                readers.append(tpe.submit(update, access_key, secret_key, region))
                region = faker.random_choices(["east", "west"], 1)[0]
                readers.append(tpe.submit(remove, access_key, secret_key, region))
                region = faker.random_choices(["east", "west"], 1)[0]
                readers.append(tpe.submit(getters, access_key, secret_key, region))
        wait(readers)


threads = []
try:
    with ThreadPoolExecutor(max_workers=2) as tpe:
        threads.append(tpe.submit(writers))
        threads.append(tpe.submit(readers))
    wait(threads)
except KeyboardInterrupt:
    os.kill(os.getpid(), 9)
