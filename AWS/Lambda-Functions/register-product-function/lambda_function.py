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
s3 = boto3.client('s3', region_name=REGION)

# Environment configuration
DEVICE_REGISTRY_TABLE = os.environ.get('DEVICE_REGISTRY_TABLE')
DEVICE_STATUS_TABLE = os.environ.get('DEVICE_STATUS_TABLE')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serializable')

def validate_required_fields(data):
    """
    Validate that all required fields are present
    
    Args:
        data (dict): Request data
        
    Returns:
        tuple: (is_valid, missing_fields)
    """
    required_fields = [
        'barcode', 'productname', 'modelno', 'serialno', 
        'manufacturerid', 'vendorid', 'buyerid', 'manufacturername'
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in data or not data[field]:
            missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields

def create_device_data_file(device_data):
    """
    Create a device data JSON file in S3 for the device
    
    Args:
        device_data (dict): Device registration data
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create device data structure for S3
        device_file_data = {
            'device_id': device_data.get('device_id', device_data['barcode']),
            'barcode': device_data['barcode'],
            'productName': device_data['productname'],
            'modelNo': device_data['modelno'],
            'serialNo': device_data['serialno'],
            'manufacturerName': device_data['manufacturername'],
            'manufacturerId': device_data['manufacturerid'],
            'vendorId': device_data['vendorid'],
            'buyerId': device_data['buyerid'],
            'registeredAt': device_data.get('registeredAt'),
            'status': 'active',
            'anomalies': [],
            'baseline_values': None
        }
        
        # S3 bucket and key (you may need to adjust based on your setup)
        bucket_name = f"iot-device-data-{REGION}"  # Adjust as needed
        s3_key = f"devices/{device_data['barcode']}/device-data.json"
        
        # Upload to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(device_file_data, default=decimal_default),
            ContentType='application/json'
        )
        
        logger.info(f"Device data file created in S3: s3://{bucket_name}/{s3_key}")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to create S3 device data file: {e}")
        # Don't fail the registration if S3 fails
        return False

def initialize_device_status(device_id):
    """
    Initialize device status record in the status table
    
    Args:
        device_id (str): Device ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        status_table = dynamodb.Table(DEVICE_STATUS_TABLE)
        
        current_time = int(time.time())
        
        # Create initial status record
        status_record = {
            'device_id': device_id,
            'timestamp': current_time,
            'connectionStatus': 'registered',
            'lastSeen': current_time,
            'registeredAt': current_time,
            'statusHistory': ['registered']
        }
        
        status_table.put_item(Item=status_record)
        logger.info(f"Device status initialized for device: {device_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize device status: {e}")
        return False

def lambda_handler(event, context):
    """
    Register a new product/device in the system
    Creates entries in both device registry and device status tables
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

    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    try:
        # Parse request body
        if not event.get('body'):
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Missing request body'})
            }

        try:
            body = json.loads(event['body'])
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid JSON in request body'})
            }

        # Validate required fields
        is_valid, missing_fields = validate_required_fields(body)
        if not is_valid:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': f'Missing fields: {", ".join(missing_fields)}'})
            }

        # Check if device already exists
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        
        try:
            existing_device = registry_table.get_item(
                Key={'barcode': body['barcode']}
            )
            
            if 'Item' in existing_device:
                return {
                    'statusCode': 409,
                    'headers': headers,
                    'body': json.dumps({'error': 'Device already registered'})
                }

        except ClientError as e:
            logger.error(f"Error checking existing device: {e}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Internal server error'})
            }

        # Prepare device registry record
        current_time = int(time.time())
        device_id = body.get('device_id', body['barcode'])  # Use barcode as device_id if not provided
        
        registry_record = {
            'barcode': body['barcode'],
            'device_id': device_id,
            'productName': body['productname'],
            'modelNo': body['modelno'],
            'serialNo': body['serialno'],
            'manufacturerName': body['manufacturername'],
            'manufacturerId': body['manufacturerid'],
            'vendorId': body['vendorid'],
            'buyerId': body['buyerid'],
            'registeredAt': current_time,
            'lastUpdated': current_time,
            'status': 'active'
        }
        
        # Add optional fields if provided
        optional_fields = ['location', 'type', 'description', 'firmware_version']
        for field in optional_fields:
            if field in body and body[field]:
                registry_record[field] = body[field]

        try:
            # Insert into device registry table
            registry_table.put_item(Item=registry_record)
            
            # Initialize device status
            status_initialized = initialize_device_status(device_id)
            
            # Create S3 device data file (optional)
            registry_record['registeredAt'] = current_time
            s3_created = create_device_data_file(registry_record)
            
            # Prepare response
            response_data = {
                'message': 'Product registered successfully',
                'device_id': device_id,
                'barcode': body['barcode'],
                'registeredAt': current_time,
                'status_initialized': status_initialized,
                's3_file_created': s3_created
            }
            
            return {
                'statusCode': 201,
                'headers': headers,
                'body': json.dumps(response_data, default=decimal_default)
            }

        except ClientError as e:
            logger.error(f"DynamoDB error during registration: {e}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Registration failed - database error'})
            }

    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Detailed error message'})
        }