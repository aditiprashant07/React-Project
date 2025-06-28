import json
import boto3
import os
import logging
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize AWS clients
REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

# Environment configuration
DEVICE_REGISTRY_TABLE = os.environ.get('DEVICE_REGISTRY_TABLE')
DEVICE_STATUS_TABLE = os.environ.get('DEVICE_STATUS_TABLE')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serializable')

def lambda_handler(event, context):
    """
    Get device metadata from device registry table
    Supports both query parameter and request body device_id
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

        # Query device registry table
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        
        try:
            # First try to get by device_id using GSI
            response = registry_table.query(
                IndexName='device-id-index',
                KeyConditionExpression='device_id = :device_id',
                ExpressionAttributeValues={':device_id': device_id}
            )
            
            if response['Items']:
                device = response['Items'][0]
            else:
                # If not found by device_id, try by barcode (primary key)
                response = registry_table.get_item(
                    Key={'barcode': device_id}
                )
                
                if 'Item' not in response:
                    return {
                        'statusCode': 404,
                        'headers': headers,
                        'body': json.dumps({'error': 'Device not found'})
                    }
                device = response['Item']

            # Convert DynamoDB item to response format
            device_response = {
                'barcode': device.get('barcode', device_id),
                'productName': device.get('productName', device.get('product_name', '')),
                'modelNo': device.get('modelNo', device.get('model_no', '')),
                'serialNo': device.get('serialNo', device.get('serial_no', '')),
                'manufacturerName': device.get('manufacturerName', device.get('manufacturer_name', '')),
                'device_id': device.get('device_id', device.get('barcode', device_id))
            }

            # Add optional fields if they exist
            optional_fields = ['manufacturerId', 'vendorId', 'buyerId', 'location', 'type']
            for field in optional_fields:
                if field in device:
                    device_response[field] = device[field]

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(device_response, default=decimal_default)
            }

        except ClientError as e:
            logger.error(f"DynamoDB error: {e}")
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