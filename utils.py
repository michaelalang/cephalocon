import base64
import json
import logging
import sys
import urllib

import urllib3

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(funcName)s: %(message)s",
    datefmt="[%Y-%m-%dT%H:%M:%S]",
)
logger = logging.getLogger(__name__)


def parse_presign_to_aws(query):
    try:
        parsed = urllib3.util.parse_url(query)
        oquy = dict(tuple(map(lambda x: x.split("="), parsed.query.split("&"))))
        for k in oquy.keys():
            oquy[k] = [urllib.parse.unquote_plus(oquy[k])]
        if oquy.get("X-Amz-Credential", False) is False:
            return oquy
        return oquy
    except:
        return {}


def parse_aws_header(header, oquy):
    algo, credential, sighead, signature = "", "", "", ""
    region = "us-east-1"
    try:
        algo, credential, sighead, signature = header.replace(",", "").split()
    except (AttributeError, ValueError) as awserr:
        logger.debug(f"cannot parse AWS header {header} {awserr}")
        if oquy.get("X-Amz-Credential", None) is not None:
            logger.debug(
                f"X-Amz-Credential Header {oquy.get('X-Amz-Credential', None)}"
            )
            algo = oquy.get("X-Amz-Algorithm", "unknown")
            credential = oquy.get("X-Amz-Credential", ["anonymous"])[0].split("/")[0]
            try:
                credential = json.loads(base64.b64decode(credential)).get("id")
            except Exception as awserr:
                # not b64encoded credentials
                logger.debug(awserr)
                pass
            region = oquy.get("X-Amz-Credential", ["user/date/us-east-1"])[0].split(
                "/"
            )[2]
            sighead = oquy.get("X-Amz-SignedHeaders", "unknown")
            signature = oquy.get("X-Amz-Signature", "unknown")

        return dict(
            algorithm=algo,
            credential=credential,
            region=region,
            headers=sighead,
            signature=signature,
        )
    try:
        credential, date, region, service, awstype = credential.split("=", 1)[-1].split(
            "/"
        )
        try:
            credential = json.loads(base64.b64decode(credential)).get("id")
        except Exception as awserr:
            logger.debug(awserr)
            # not b64encoded credentials
            pass
    except ValueError as awserr:
        logger.debug(f"cannot parse credential header {credential} {awserr}")
    try:
        sighead = sighead.split("=")[-1]
    except ValueError as awserr:
        logger.debug(f"cannot parse signatureheaders header {sighead} {awserr}")
    try:
        signature = signature.split("=")[-1]
    except ValueError as awserr:
        logger.debug(f"cannot parse signature header {signature} {awserr}")

    return dict(
        algorithm=algo,
        credential=credential,
        region=region,
        headers=sighead,
        signature=signature,
    )


def parse_bucket(path, opar):
    try:
        bucket = path.split("/")[1]
        if "?" in bucket:
            bucket = bucket.split("?")[0]
    except IndexError:
        bucket = path.split("?")[0]
    except Exception as bucerr:
        logger.debug(f"parse bucket from Path exception {path} {bucerr}")
        bucket = opar.get("headers").get(":path")
    if bucket == "":
        # list-all-buckets method
        bucket = "*"
    return bucket


def parse_requests_data(data):
    try:
        logger.debug(f"parse_requests_data in: {data}")
        opar = data["attributes"]["request"]["http"]
        oquy = data.get("parsed_query", {})
        if oquy == {}:
            oquy = parse_presign_to_aws(opar.get("path"))
        authority = opar.get("headers", {}).get(
            ":authority", opar.get("headers").get("host")
        )
        auth = parse_aws_header(opar.get("headers", {}).get("authorization", ""), oquy)
        bucket = parse_bucket(opar.get("headers", {}).get(":path"), opar)
        logger.debug(f"parse_requests_data bucket: {bucket} auth {auth}")
        method = opar.get("headers", {}).get(":method")
        source = data["attributes"]["source"]["address"]["socketAddress"]["address"]

        def querysplit(content):
            content = content.split("&")
            for key, value in map(lambda x: x.split("="), content):
                yield key, urllib.parse.unquote_plus(value)

        # check presigned v2 and v4
        try:
            presign = dict(querysplit(opar.get("headers", {}).get(":path")))
        except Exception as preerr:
            logger.debug(preerr)
            presign = {}
        if all(
            [
                presign.get("X-Amz-Algorithm", False),
                presign.get("X-Amz-Credential", False),
                presign.get("X-Amz-Date", False),
                presign.get("X-Amz-Expires", False),
                presign.get("X-Amz-SignedHeaders", False),
                presign.get("X-Amz-Signature"),
            ]
        ):
            try:
                auth["credential"] = presign.get("X-Amz-Credential").split("/")[0]
            except Exception as preerr:
                logger.debug(
                    f"Presign ERROR {preerr} {presign.get('X-Amz-Credential')}"
                )

            try:
                auth["region"] = presign.get(
                    "X-Amz-Credential", "anonymous/date/us-east-1"
                ).split("/")[2]
            except Exception as preerr:
                logger.debug(
                    f"Presign ERROR {preerr} {presign.get('X-Amz-Credential')}"
                )

        elif all(
            [
                presign.get("AWSAccessKeyId", False),
                presign.get("Signature", False),
                presign.get("Expires", False),
            ]
        ):
            auth["credential"] = presign.get("AWSAccessKeyId")
            auth["region"] = "us-east-1"
        try:
            length = int(opar.get("headers").get("content-length"))
        except TypeError:
            length = 0
        return dict(
            region=auth.get("region", "us-east-1"),
            user=auth.get("credential", "anonymous"),
            bucket=bucket,
            method=method,
            source=source,
            authority=authority,
            length=length,
        )
    except Exception as err:
        logger.debug(f"Error {err}")
        logger.debug(f"parse_requests_data: {data}")
        return dict(
            region="us-east-1",
            user="anonymous",
            bucket="unknown",
            method="unknown",
            source="unknown",
            authority="unknown",
            length=0,
        )
