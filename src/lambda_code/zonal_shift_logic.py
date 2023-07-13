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
my_session = boto3.session.Session()
Region = my_session.region_name
topicARN = getenv("TopicArn")
shift_expire = getenv("ShiftExpiration")
notification = {}

# Initialize sdk
elb = boto3.client('elbv2', region_name=Region)
arcshift = boto3.client('arc-zonal-shift')
sns = boto3.client('sns', region_name=Region)


# Functions
def handler(event, context):
    """Handler Function
    """
    if not event['Records'][0]['messageId']:
        logger.warn('No message in the SQS Queue. Aborting.')
        return
    elif 'elb_arn' and 'az_id' not in event['Records'][0]['body']:
        logger.warn('Message not properly structured. Aborting.')
        return
    else:
        msg_body = event['Records'][0]['body']
        msg = json.loads(msg_body)
        elb_arn = msg['elb_arn']
        az = msg['az_id']

    # Start Zonal Shift

    shift = start_shift(elb_arn, az)
    if shift is None:
        logger.error("""Unable to start shift for {dns_name}. \
            Please check the logs""")
        notification['Title'] = f'Failed to start Zonal Shift for AZ: {az}'
        notify(notification)
    else:
        notification['Title'] = f'Zonal Shift Started for AZ: {az}'
        notification['ZonalShiftID'] = shift['zonalShiftId']
        notification['DegradedAZ'] = shift['awayFrom']
        notification['Reason'] = shift['comment']
        notification['StartTime'] = shift['startTime']
        notification['EndTime'] = shift['expiryTime']
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


def notify(notice):
    """This functions sends notifications
    """
    try:
        response = sns.publish(
            TopicArn=topicARN,
            Message=str(notification),
            Subject=notice['Title']
        )
        messageId = response['MessageId']
        logger.info(f'Notification sent with Message ID:{messageId}')
    except (exceptions.ClientError, exceptions.ParamValidationError) as e:
        logger.error(e)
