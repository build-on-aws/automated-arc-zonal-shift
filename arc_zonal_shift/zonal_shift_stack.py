# Core code to deploy lambda function ans sns topic
from aws_cdk import (
    Duration,
    Stack,
    aws_sns as _sns,
    aws_sqs as _sqs,
    aws_lambda as _lambda,
    aws_lambda_event_sources as _events,
    aws_iam as _iam,
    CfnParameter,
    CfnOutput
)
from constructs import Construct


class ZonalShiftAppStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SQS Standard Queue for receiving monitoring
        # payload

        queue = _sqs.Queue(
            self,
            "Queue",
            encryption=_sqs.QueueEncryption.KMS_MANAGED,
            visibility_timeout=Duration.seconds(300)
        )

        # The code that defines your stack goes here
        # SNS Topic creation
        topic = _sns.Topic(
            self,
            "ZonalShiftTopic",
        )

        # Parameters
        shift_exp = CfnParameter(
            self,
            "shift_duration",
            default="5",
            type="String"
        )
        topic_arn = topic.topic_arn
        queue_url = queue.queue_url

        # Lambda Function code
        with open("../automated-arc-zonal-shift/src/lambda_code/zonal_shift_logic.py", encoding="utf8") as fp:
            code = fp.read()

        fn = _lambda.Function(
            self,
            "ZonalShiftFunction",
            handler="index.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.InlineCode(code),
            timeout=Duration.minutes(5),
            environment={
                "ShiftExpiration": shift_exp.value_as_string,
                "TopicArn": topic_arn,
                "QueueUrl": queue_url
            },
            dead_letter_queue_enabled=True
        )

        # Permissions
        # - Lambda Publish permission
        topic.grant_publish(fn)

        # - SQS Lambda trigger permission
        event_source = _events.SqsEventSource(queue)
        fn.add_event_source(event_source)

        # - Lambda Execution permission
        role = fn.role
        role.add_to_policy(_iam.PolicyStatement(
            effect=_iam.Effect.ALLOW,
            resources=["*"],
            actions=[
                "elasticloadbalancing:DescribeLoadBalancers",
                "arc-zonal-shift:ListManagedResources",
                "arc-zonal-shift:StartZonalShift"
            ],
        )
        )

        # Output Resource Information
        CfnOutput(
            self,
            "QueueUrl",
            value=queue_url
        )
        CfnOutput(
            self,
            "SnsTopic",
            value=topic_arn
        )
