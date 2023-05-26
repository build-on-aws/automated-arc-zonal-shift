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
    elif 'Degraded_LB' not in event['Records'][0]['body']:
        logger.warn('Message not properly structured. Aborting.')
        return
    else:
        msg_body = event['Records'][0]['body']
        msg = json.loads(msg_body)
        dns_name = msg['Degraded_LB']
    lb_name = get_elb(dns_name)
    if lb_name is None:
        logger.error(
            """Load Balancer Not Found. \
            Please check the logs for more info."""
        )
        return

    shift = start_shift(dns_name=lb_name)
    if shift is None:
        logger.error("""Unable to start shift for {dns_name}. \
            Please check the logs""")
        notification['Title'] = f'Failed to start Zonal Shift for {dns_name}'
        notify(notification)
    else:
        notification['Title'] = f'Zonal Shift Started for {dns_name}'
        notification['ZonalShiftID'] = shift['zonalShiftId']
        notification['DegradedAZ'] = shift['awayFrom']
        notification['Reason'] = shift['comment']
        notification['StartTime'] = shift['startTime']
        notification['EndTime'] = shift['expiryTime']
        notify(notification)


def start_shift(dns_name):
    """This functions starts the zonal shift to
    shift traffic away from the degraded AZ.
    """
    arn = get_zonal_shift_resources(dns_name)[0]
    az = get_zonal_shift_resources(dns_name)[1]
    try:
        response = arcshift.start_zonal_shift(
            awayFrom=str(az[0]),
            comment='Shifting traffic away from degraded workload',
            expiresIn=shift_expire,
            resourceIdentifier=arn
        )
        return response
    except (exceptions.ClientError, exceptions.ParamValidationError) as e:
        logger.error(e)
        return None
    except exceptions as e:
        logger.error(e)
        return None


def get_zonal_shift_resources(dns_name):
    """This function checks if the Load Balancer is
    managed by Zonal Shift then returns the ARN and
    the corresponding Availability Zone.
    """
    try:
        paginator = arcshift.get_paginator('list_managed_resources')
        page_iterator = paginator.paginate()
        for page in page_iterator:
            for i in page['items']:
                lb_name = i['name']
                if dns_name == lb_name:
                    arn = i['arn']
                    az = i['availabilityZones']
                    return arn, az
        print('Resource not in managed resources')
        return None
    except exceptions.ClientError as e:
        print(e)
        return None


def get_elb(name):
    """This function retrieves and returns the
    DNS name of the provided Load Balancer
    """
    try:
        paginator = elb.get_paginator('describe_load_balancers')
        page_iterator = paginator.paginate()
        for page in page_iterator:
            for i in page['LoadBalancers']:
                if i['DNSName'] == name:
                    lb_name = i['LoadBalancerName']
                    return lb_name
        print(f'Load Balancer with DNS name {name} was not found')
        return None
    except exceptions.ClientError as e:
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
