# Route53 ARC Zonal Shift

This project creates a Lambda function, an SQS queue, and an SNS Topic. The Lambda function is triggered \
by a message published to the SQS queue. The Lambda function makes an API call to start Zonal Shift and 
sends a success or failure message to the SNS topic

![ARC ZONAL SHIFT](images/zonal-shift-sample-solution.png "Figure 1. Automated Zonal Shift Diagram")

## Solution Workflow

1. The App Server lost network access to the Database. The NLB still sees the App Server as healthy and continues to send requests to it. Client requests are failing with 5XX errors. A Gray Failure has occurred in the AZ.
2. The Application monitoring mechanism detects the gray failure. A message is sent to the SQS queue.
3. The SQS queue triggers a Lambda Function with information about the degraded AZ.
4. The Lambda function makes an API call to start Route 53 ARC Zonal Shift.
5. Route 53 ARC Zonal Shift shifts traffic from the degraded AZ.
6. The Lambda function publishes a message to an SNS topic for notification.

## Deployment Steps

1. Ensure CDK is installed
```
$ npm install -g aws-cdk
```

2. Create a Python virtual environment

```
$ python3 -m venv .venv
```

3. Activate virtual environment

_On MacOS or Linux_
```
$ source .venv/bin/activate
```

_On Windows_
```
% .venv\Scripts\activate.bat
```

4. Install the required dependencies.

```
$ pip install -r requirements.txt
```

5. Synthesize (`cdk synth`) or deploy (`cdk deploy`) the example

```
$ cdk deploy
```

After the deployment, you should see an **Output** with the values for the `QueueUrl` and the `SnsTopic`. Please copy them, you will need them later.

## Testing the Solution
1. From the root directory change to src/sample.

    ```bash
    cd src/sample
    ```

2. Edit the payload.json file. Change the value of `elb_arn` and `az_id` to your load balancer's Amazon Resource Name (ARN) and Availability Zone ID respectively.
`DO NOT` change any of the Keys.

    ```bash
    vi payload.json
    ```

3. Log into the AWS console, navigate to the Load Balancer page and note the status of the NLB as indicated below. Note that there is no column labelled for Zonal Shift.

   ![pre-shift](images/before-zonal-shift.png)

4. [Subscribe](https://docs.aws.amazon.com/sns/latest/dg/sns-create-subscribe-endpoint-to-topic.html?sc_channel=el&sc_campaign=devopswave&sc_geo=mult&sc_country=mult&sc_outcome=acq&sc_content=arc-zonal-shift) to the SNS topic saved from the deployment step (optional). Replace the placeholder `QUEUE_URL_HERE` in step 5 (below) with the value of `QueueUrl` saved from the deployment step.

5. Trigger the Zonal Shift by running the command below

    ```bash
    aws sqs send-message --queue-url *QUEUE_URL_HERE* --message-body file://payload.json
    ```

6. To verify the shift, log back into the Load Balancer page in the AWS Console and verify the status of the NLB. Note that new columns have appeared for Zonal Shift as indicated below. If you subscribed to the SNS topic, you will also receive an SNS notification.

   ![post-shift](images/after-zonal-shift.png)
```

## Cleaning Up

```
$ cdk destroy

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
