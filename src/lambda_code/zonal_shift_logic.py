'''
This Lambda function is triggered by an SQS Queue to
respond to application gray failures. The function
starts Route53 ARC Zonal Shift then publishes to an
SNS topic for notifications.
'''
import boto3
import json
from botocore import exceptions
import logging
from os import getenv

# Set Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Set the variables
region = getenv("AWS_REGION")
topicARN = getenv("TopicArn")
shift_expire = getenv("ShiftExpiration")

# Initialize sdk
elb = boto3.client('elbv2', region_name=region)
arcshift = boto3.client('arc-zonal-shift')
sns = boto3.client('sns', region_name=region)


# Functions
def handler(event, context):
    """Handler Function
    """
    if not event['Records'][0]['messageId']:
        logger.error('No message in the SQS Queue. Aborting.')
        return
    try:
        msg_body = event['Records'][0]['body']
        msg = json.loads(msg_body)
        elb_arn = msg['elb_arn']
        az = msg['az_id']
    except:
        logger.error('Message not properly structured. Aborting.')
        return

    # Start Zonal Shift

    notification = {}
    shift = start_shift(elb_arn, az)
    if shift is None:
        logger.error(f"""Unable to start shift for ELB: {elb_arn} in AZ: {az}. \
            Please check the logs""")
        notification['Subject'] = "Zonal Shift Notification - Error occurred."
        notification['Title'] = f'Failed to start Zonal Shift for ELB: {elb_arn} in AZ: {az}'
        notify(notification)
    else:
        logger.info(f'Zonal Shift Started for ELB: {elb_arn} in AZ: {az}')
        notification['Subject'] = "Zonal Shift Notification - Shift started."
        notification['Title'] = f'Zonal Shift Started for ELB: {elb_arn} in AZ: {az}'
        notification['ZonalShiftID'] = shift['zonalShiftId']
        notification['DegradedAZ'] = shift['awayFrom']
        notification['Reason'] = shift['comment']
        notification['StartTime'] = str(shift['startTime'])
        notification['EndTime'] = str(shift['expiryTime'])
        notify(notification)


def start_shift(elb_arn, az):
    """This functions starts the zonal shift to
    shift traffic away from the degraded AZ.
    """
    try:
        response = arcshift.start_zonal_shift(
            awayFrom=az,
            comment='Shifting traffic away from degraded workload',
            expiresIn=shift_expire,
            resourceIdentifier=elb_arn
        )
        return response
    except (exceptions.ClientError, exceptions.ParamValidationError) as e:
        logger.error(e)
        return None
    except exceptions as e:
        logger.error(e)
        return None


def notify(notification):
    """This functions sends notifications
    """
    try:
        response = sns.publish(
            TopicArn=topicARN,
            Message=str(notification),
            Subject=notification['Subject']
        )
        messageId = response['MessageId']
        logger.info(f'Notification sent with Message ID:{messageId}')
    except (exceptions.ClientError, exceptions.ParamValidationError) as e:
        logger.error(e)
