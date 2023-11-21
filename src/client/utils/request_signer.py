# Copyright Krzysztof Wilczynski, Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
from http import HTTPMethod
from typing import Any, Dict

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest, AWSResponse
from botocore.httpsession import URLLib3Session


class RequestSigner:
    """
    A class to encapsulate native AWS (Boto3) V4 signing
    mechanism for HTTP urllib3 requests
    """

    def __init__(
        self,
        base_url: str,
        service_name: str = "execute-api",
        response_encoding: str = "utf-8",
        boto3_session: boto3.Session = boto3.Session(),
        urllib_session: URLLib3Session = URLLib3Session(
            proxies={
                "https": os.environ.get("https_proxy", ""),
                "http": os.environ.get("https_proxy", ""),
            }
        ),
    ):
        if not base_url:
            logging.error(
                "API Gateway base url is not configured. Please make sure that the "
                "requried setup (API Gateway and SSM Parameters) are present in the "
                "target AWS account."
            )
            raise Exception(
                "Backend failure - could not determine the target API. Please contact support."
            )

        self.base_url = base_url

        self.service_name = service_name
        self.response_encoding = response_encoding

        self.boto3_session = boto3_session
        self.urllib_session = urllib_session

        self.aws_credentials = self.boto3_session.get_credentials()
        self.aws_region_name = self.boto3_session.region_name

    def make_signed_request(
        self,
        http_method: HTTPMethod | str,
        path: str = "",
        data: Any = {},
        params: Dict[str, str] = {},
        headers: Dict[str, str] = {"Content-Type": "application/x-amz-json-1.1"},
    ) -> AWSResponse:
        """
        Signs and sends an AWS V4 Signed request that is then resolved by AWS
        backend (typically API Gateways) into IAM credentials for advanced authorization

        Arguments:
            http_method -- HTTP method of the request
            path -- path of the REST request (following the base_url, MUST start with a slash)

        Keyword Arguments:
            data -- optional, request body (default: {{}})
            params -- optional, request query parameters (default: {{}})
            headers -- optional, request headers (default: {{}})

        Returns:
            response (botocore.awsrequest.AWSResponse object)
        """
        request_url = self.base_url + path

        http_method_str = (
            http_method.value if type(http_method) is HTTPMethod else http_method
        )

        logging.debug(
            "Using the following proxy configuration for REST requests: "
            f"{json.dumps(self.urllib_session._proxy_config._proxies)}"
        )

        # Catch URL configuration issues before cryptic errors
        # are thrown by SigV4Auth(...).add_auth() call
        if "https://" not in request_url:
            raise Exception("Request URL should start with 'https://'")

        if isinstance(data, dict):
            data = json.dumps(data, default=str)

        aws_request = AWSRequest(
            method=http_method_str,
            url=request_url,
            data=data,
            params=params,
            headers=headers,
        )

        SigV4Auth(
            credentials=self.aws_credentials,
            service_name=self.service_name,
            region_name=self.aws_region_name,
        ).add_auth(aws_request)

        prepared_request = aws_request.prepare()

        try:
            response: AWSResponse = self.urllib_session.send(prepared_request)

        except Exception as e:
            logging.error(f"Error calling AWS endpoint ({request_url}): {e}")
            raise

        return response
