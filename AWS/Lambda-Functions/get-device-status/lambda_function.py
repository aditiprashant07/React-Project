import json
import boto3
import os
import logging
import time
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize AWS clients
REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)

# Environment configuration
DEVICE_STATUS_TABLE = os.environ.get('DEVICE_STATUS_TABLE')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serializable')

def determine_connection_status(latest_status, current_time):
    """
    Determine connection status based on latest status record
    
    Args:
        latest_status (dict): Latest status record from DynamoDB
        current_time (int): Current timestamp
        
    Returns:
        str: Connection status ('connected', 'disconnected', 'unknown')
    """
    if not latest_status:
        return 'unknown'
    
    # Get the timestamp of the latest status
    status_timestamp = latest_status.get('timestamp', 0)
    
    # If the latest status is more than 5 minutes old, consider it disconnected
    five_minutes_ago = current_time - (5 * 60)
    
    if status_timestamp < five_minutes_ago:
        return 'disconnected'
    
    # Check if there's an explicit connection status
    explicit_status = latest_status.get('connectionStatus')
    if explicit_status:
        return explicit_status.lower()
    
    # If we have recent data, assume connected
    return 'connected'

def lambda_handler(event, context):
    """
    Get device connectivity status from device status table
    Returns the current connection status of the device
    """
    
    # CORS headers
    headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent,X-Requested-With,Accept,Accept-Language,Content-Language,Cache-Control,Pragma',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
    'Access-Control-Allow-Credentials': 'false',
    'Access-Control-Max-Age': '86400'
    }

    try:
        # Handle CORS preflight
        if event.get('httpMethod') == 'OPTIONS':
            return {'statusCode': 200, 'headers': headers, 'body': ''}

        # Extract device_id from query parameters or request body
        device_id = None
        
        # Try query parameters first
        query_params = event.get('queryStringParameters') or {}
        device_id = query_params.get('device_id')
        
        # If not found, try request body
        if not device_id and event.get('body'):
            try:
                body = json.loads(event['body'])
                device_id = body.get('device_id')
            except json.JSONDecodeError:
                pass

        if not device_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Missing device_id'})
            }

        # Query device status table
        status_table = dynamodb.Table(DEVICE_STATUS_TABLE)
        
        try:
            # Get the most recent status record for this device
            response = status_table.query(
                KeyConditionExpression='device_id = :device_id',
                ExpressionAttributeValues={':device_id': device_id},
                ScanIndexForward=False,  # Get most recent first
                Limit=1
            )
            
            current_time = int(time.time())
            
            if not response['Items']:
                # No status records found - could be a new device
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': 'Device not found'})
                }
            
            latest_status = response['Items'][0]
            connection_status = determine_connection_status(latest_status, current_time)
            
            # Build response
            response_data = {
                'barcode': device_id,  # Use device_id as barcode for consistency
                'connectionStatus': connection_status
            }
            
            # Add additional status information if available
            if 'lastSeen' in latest_status:
                response_data['lastSeen'] = latest_status['lastSeen']
            
            if 'lastHeartbeat' in latest_status:
                response_data['lastHeartbeat'] = latest_status['lastHeartbeat']
                
            if 'ipAddress' in latest_status:
                response_data['ipAddress'] = latest_status['ipAddress']
                
            if 'signalStrength' in latest_status:
                response_data['signalStrength'] = latest_status['signalStrength']
            
            # Add timestamp of when this status was determined
            response_data['statusCheckedAt'] = current_time

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(response_data, default=decimal_default)
            }

        except ClientError as e:
            logger.error(f"DynamoDB error: {e}")
            
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': 'Device not found'})
                }
            else:
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps({'error': 'Internal server error'})
                }

    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Detailed error message'})
        }