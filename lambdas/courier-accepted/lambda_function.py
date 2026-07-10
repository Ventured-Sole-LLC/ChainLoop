import json
import boto3
import os
import time
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
eventbridge = boto3.client('events')

event_log_table = dynamodb.Table(os.environ['EVENT_LOG_TABLE_NAME'])
projection_table = dynamodb.Table(os.environ['PROJECTION_TABLE_NAME'])
EVENT_BUS_NAME = os.environ['EVENT_BUS_NAME']

ALLOWED_GROUPS = {'courier'}
REQUIRED_PRIOR_STATUS = 'COLLECTED'
NEW_STATUS = 'ACCEPTED'


def log(level, message, **fields):
    print(json.dumps({'level': level, 'message': message, 'endpoint': 'courier-accepted', **fields}))


def lambda_handler(event, context):
    start_time = time.time()
    lambda_request_id = context.aws_request_id

    body = json.loads(event.get('body') or '{}')
    specimen_id = body.get('specimen_id')
    timestamp = body.get('timestamp')
    idempotency_key = body.get('idempotency_key')

    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    groups_raw = claims.get("cognito:groups", "")
    caller_groups = [g.strip() for g in groups_raw.strip("[]").split(",")] if groups_raw else []
    caller_sub = claims.get("sub")

    if not any(group in ALLOWED_GROUPS for group in caller_groups):
        log('WARN', 'Rejected unauthorized courier accept attempt',
            lambda_request_id=lambda_request_id, caller_sub=caller_sub)
        return {'statusCode': 403, 'body': json.dumps({'error': 'Caller is not authorized to accept custody'})}

    if not specimen_id or not timestamp or not idempotency_key:
        log('WARN', 'Rejected request missing required fields', lambda_request_id=lambda_request_id)
        return {'statusCode': 400, 'body': json.dumps({'error': 'specimen_id, timestamp, and idempotency_key are required'})}

    try:
        response = projection_table.get_item(Key={'specimen_id': specimen_id, 'record_type': 'SUMMARY'})
    except ClientError as e:
        log('ERROR', 'Failed to read projection', lambda_request_id=lambda_request_id, specimen_id=specimen_id, error=str(e))
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to look up specimen, please try again'})}

    current_item = response.get('Item')
    if not current_item:
        log('WARN', 'Specimen not found', lambda_request_id=lambda_request_id, specimen_id=specimen_id)
        return {'statusCode': 404, 'body': json.dumps({'error': 'Specimen not found'})}

    if current_item.get('current_status') != REQUIRED_PRIOR_STATUS:
        log('WARN', 'Rejected illegal transition', lambda_request_id=lambda_request_id, specimen_id=specimen_id,
            current_status=current_item.get('current_status'))
        return {'statusCode': 409, 'body': json.dumps({
            'error': f"Cannot accept custody. Current status: {current_item.get('current_status')}, expected: {REQUIRED_PRIOR_STATUS}"
        })}

    event_type = "CourierAccepted"
    sort_key = f"{timestamp}#{event_type}#{idempotency_key}"

    try:
        event_log_table.put_item(
            Item={
                'specimen_id': specimen_id,
                'timestamp_event_type_event_id': sort_key,
                'event_type': event_type,
                'accepted_by': caller_sub,
                'timestamp': timestamp,
            },
            ConditionExpression='attribute_not_exists(timestamp_event_type_event_id)'
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            log('INFO', 'Duplicate scan detected, ignoring retry', lambda_request_id=lambda_request_id, specimen_id=specimen_id)
            return {'statusCode': 200, 'body': json.dumps({'message': 'Already recorded', 'specimen_id': specimen_id})}
        log('ERROR', 'Failed to write CourierAccepted event', lambda_request_id=lambda_request_id, error=str(e))
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to record courier acceptance, please try again'})}

    try:
        projection_table.update_item(
            Key={'specimen_id': specimen_id, 'record_type': 'SUMMARY'},
            UpdateExpression='SET current_status = :s, last_event_at = :t, current_owner = :o',
            ExpressionAttributeValues={':s': NEW_STATUS, ':t': timestamp, ':o': caller_sub}
        )
        eventbridge.put_events(Entries=[{
            'Source': 'chainloop.custody',
            'DetailType': event_type,
            'Detail': json.dumps({'specimen_id': specimen_id, 'event_type': event_type, 'accepted_by': caller_sub, 'timestamp': timestamp}),
            'EventBusName': EVENT_BUS_NAME,
        }])
    except ClientError as e:
        log('ERROR', 'Persisted event but failed to update projection or publish', lambda_request_id=lambda_request_id, specimen_id=specimen_id, error=str(e))
        return {'statusCode': 500, 'body': json.dumps({'error': 'Recorded but failed to fully process, contact support', 'specimen_id': specimen_id})}

    log('INFO', 'Courier acceptance recorded successfully', lambda_request_id=lambda_request_id, specimen_id=specimen_id,
        duration_ms=round((time.time() - start_time) * 1000, 2))
    return {'statusCode': 200, 'body': json.dumps({'message': 'Courier acceptance recorded', 'specimen_id': specimen_id})}