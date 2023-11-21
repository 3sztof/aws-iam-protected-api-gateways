import json
import logging
from http import HTTPMethod
from os import environ

import boto3
from mypy_boto3_sts import STSClient
from utils.request_signer import RequestSigner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

if __name__ == "__main__":
    client_role_arn = environ.get("CLIENT_ROLE_ARN", "") or input(
        "Client IAM Role ARN to be assumed by the script "
        "(input here or set through environment variable - CLIENT_ROLE_NAME, "
        "if left empty, the the script will run with the current shell session's "
        "AWS credentials): "
    )

    if client_role_arn:
        sts_client: STSClient = boto3.client("sts")  # type: ignore

        logger.info(f"Using AWS Boto3 STS client to assume role: {client_role_arn}")

        assume_role_response = sts_client.assume_role(
            RoleArn=client_role_arn, RoleSessionName="APIClientSession"
        )

        assumed_role_credentials = assume_role_response["Credentials"]

        boto3_session = boto3.Session(
            aws_access_key_id=assumed_role_credentials["AccessKeyId"],
            aws_secret_access_key=assumed_role_credentials["SecretAccessKey"],
            aws_session_token=assumed_role_credentials["SessionToken"],
        )
    else:
        logger.info("No custom role ARN provided, using the shell's AWS credentials")
        boto3_session = boto3.Session()

    api_gateway_url = environ.get("API_URL", "") or input(
        "Api Gateway URL (input here or set through "
        "environment variable - API_URL): "
    )

    if not api_gateway_url:
        raise Exception("No valid API Gateway url was provided")

    request_signer = RequestSigner(
        base_url=api_gateway_url, boto3_session=boto3_session
    )

    request_path = (
        input("Provide API request path (leave empty to choose 'test' path): ")
        or "test"
    )
    request_data = json.loads(
        input(
            "Provide API request body - data in JSON format (leave "
            "empty to send a request with an empty body): "
        )
        or "{}"
    )
    request_params = json.loads(
        input(
            "Provide request query parameters in JSON format (leave "
            "empty to skip sending query parameters): "
        )
        or "{}"
    )
    request_headers = json.loads(
        input(
            "Provide custom request headers in JSON format (leave "
            "empty to send default headers): "
        )
        or "{}"
    )

    response = request_signer.make_signed_request(
        http_method=HTTPMethod.POST,
        path=request_path,
        data=request_data,
        params=request_params,
        headers=request_headers,
    )

    print(f"\nResponse status code: {response.status_code}")
    print("\nDecoded (utf-8) response content:")
    print(json.dumps(json.loads(response.content.decode("utf-8")), indent=2))
