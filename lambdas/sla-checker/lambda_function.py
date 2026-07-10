import json
import boto3
import os
import time
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
eventbridge = boto3.client('events')

projection_table = dynamodb.Table(os.environ['PROJECTION_TABLE_NAME'])
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
EVENT_BUS_NAME = os.environ['EVENT_BUS_NAME']

ACTIVE_STATUSES = ['COLLECTED', 'ACCEPTED', 'IN_TRANSIT']


def log(level, message, **fields):
    print(json.dumps({'level': level, 'message': message, 'endpoint': 'sla-checker', **fields}))


def lambda_handler(event, context):
    start_time = time.time()
    lambda_request_id = context.aws_request_id
    now = datetime.now(timezone.utc).isoformat()

    overdue_specimens = []

    for status in ACTIVE_STATUSES:
        try:
            response = projection_table.query(
                IndexName='status-sla-index',
                KeyConditionExpression=Key('current_status').eq(status) & Key('sla_due_at').lte(now)
            )
            items = response.get('Items', [])
            overdue_specimens.extend(items)
        except Exception as e:
            log('ERROR', 'Failed to query status-sla-index for status', lambda_request_id=lambda_request_id, status=status, error=str(e))
            continue

    log('INFO', 'SLA check completed', lambda_request_id=lambda_request_id, overdue_count=len(overdue_specimens),
        duration_ms=round((time.time() - start_time) * 1000, 2))

    for specimen in overdue_specimens:
        specimen_id = specimen.get('specimen_id')
        current_status = specimen.get('current_status')
        sla_due_at = specimen.get('sla_due_at')
        escalation_status = specimen.get('escalation_status', 'NONE')

        if escalation_status == 'ESCALATED':
            log('INFO', 'Specimen already escalated, skipping', lambda_request_id=lambda_request_id, specimen_id=specimen_id)
            continue

        try:
            projection_table.update_item(
                Key={'specimen_id': specimen_id, 'record_type': 'SUMMARY'},
                UpdateExpression='SET escalation_status = :e',
                ExpressionAttributeValues={':e': 'ESCALATED'}
            )

            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"ChainLoop SLA Breach: {specimen_id}",
                Message=(
                    f"Specimen {specimen_id} has missed its SLA window.\n"
                    f"Current status: {current_status}\n"
                    f"SLA due at: {sla_due_at}\n"
                    f"Checked at: {now}"
                )
            )

            eventbridge.put_events(Entries=[{
                'Source': 'chainloop.custody',
                'DetailType': 'SlaBreached',
                'Detail': json.dumps({
                    'specimen_id': specimen_id,
                    'event_type': 'SlaBreached',
                    'current_status': current_status,
                    'sla_due_at': sla_due_at,
                    'checked_at': now,
                }),
                'EventBusName': EVENT_BUS_NAME,
            }])

            log('WARN', 'SLA breach escalated', lambda_request_id=lambda_request_id, specimen_id=specimen_id,
                current_status=current_status, sla_due_at=sla_due_at)
        except Exception as e:
            log('ERROR', 'Failed to escalate overdue specimen', lambda_request_id=lambda_request_id, specimen_id=specimen_id, error=str(e))

    return {'statusCode': 200, 'body': json.dumps({'overdue_count': len(overdue_specimens)})}