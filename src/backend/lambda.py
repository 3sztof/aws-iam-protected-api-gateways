import json


def handler(event, context):
    response = {
        "info": "This is a response body from the backend Lambda function",
        "lambda_received_event": event,
    }
    return {"statusCode": 200, "body": json.dumps(response)}
