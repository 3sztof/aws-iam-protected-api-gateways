import os

from aws_cdk import (
    App,
    Arn,
    ArnComponents,
    Aws,
    CfnOutput,
    Environment,
    Stack,
    aws_apigateway,
    aws_iam,
    aws_lambda,
)
from constructs import Construct


class DemoStack(Stack):
    def __init__(self, scope: Construct, id: str, env: Environment, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # IAM Role for the client applications
        # (credentials for generating the AWS V4 Signatures for client requests)
        api_user_role = aws_iam.Role(
            self,
            "API-User-Role",
            assumed_by=aws_iam.AccountPrincipal(env.account),
        )

        # Simple AWS Lambda backend to produce API responses
        backend_lambda = aws_lambda.Function(
            self,
            "Backend-Lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            handler="lambda.handler",
            code=aws_lambda.Code.from_asset(
                path=os.path.join(os.path.dirname(__file__), "../../backend")
            ),
        )

        # Prepare an ARN principal object of the API Client's IAM Role for API Policy Document
        client_role_arn_principal = aws_iam.ArnPrincipal(arn=api_user_role.role_arn)

        # Rest API Gateway endpoint setup
        api = aws_apigateway.RestApi(
            self,
            "API",
            rest_api_name="IAMProtectedAPI",
            policy=aws_iam.PolicyDocument(
                statements=[
                    aws_iam.PolicyStatement(
                        effect=aws_iam.Effect.DENY,
                        principals=[aws_iam.AnyPrincipal()],
                        actions=["execute-api:Invoke"],
                        resources=["execute-api:/*/*/denied"],
                    ),
                    aws_iam.PolicyStatement(
                        effect=aws_iam.Effect.DENY,
                        not_principals=[client_role_arn_principal],
                        actions=["execute-api:Invoke"],
                        resources=["execute-api:/*/*/*"],
                    ),
                    aws_iam.PolicyStatement(
                        effect=aws_iam.Effect.ALLOW,
                        principals=[client_role_arn_principal],
                        actions=["execute-api:Invoke"],
                        resources=["execute-api:/*/*/*"],
                    ),
                ]
            ),
        )
        api_resource = api.root.add_resource("{proxy+}")
        api_resource.add_method(
            http_method="ANY",
            integration=aws_apigateway.LambdaIntegration(
                handler=backend_lambda, proxy=True
            ),
            authorization_type=aws_apigateway.AuthorizationType.IAM,
        )

        # Add API execution permission to the client IAM Role
        # (has to be done after API creation due to API policy statement principal verification)
        api_user_role.add_to_policy(
            statement=aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=["execute-api:Invoke"],
                resources=[
                    Arn.format(
                        stack=self,
                        components=ArnComponents(
                            resource=api.rest_api_id,
                            service="execute-api",
                            resource_name=f"{api.deployment_stage.stage_name}/*/*/*",
                        ),
                    )
                ],
            )
        )
        # Create CloudFormation outputs for ease of endpoint testing
        CfnOutput(
            self,
            "ClientRoleARN",
            value=api_user_role.role_arn,
            description="ARN of the API client IAM Role, use it to invoke the API",
        )


app = App()
deployment_env = Environment(
    account=os.environ.get("AWS_DEFAULT_ACCOUNT", Aws.ACCOUNT_ID),
    region=os.environ.get("CDK_DEFAULT_REGION", Aws.REGION),
)
DemoStack(app, "IAM-API-Security-Demo-Stack", env=deployment_env)
app.synth()
