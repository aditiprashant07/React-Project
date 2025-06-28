import json
import boto3
import time
from datetime import datetime
import logging
import os
from decimal import Decimal
import uuid

# Configure logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Initialize AWS clients
try:
    REGION = os.environ.get('REGION', 'ap-northeast-1')
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    logger.info("AWS clients initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AWS clients: {str(e)}")
    raise

# Configuration from environment variables
DEVICE_METADATA_TABLE = os.environ.get('DEVICE_METADATA_TABLE', 'DeviceMetadata')
DEVICE_REGISTRY_TABLE = os.environ.get('DEVICE_REGISTRY_TABLE', 'DeviceRegistration')

def decimal_default(obj):
    """Helper function to convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)

def convert_to_decimal(value):
    """Safely convert numeric values to Decimal for DynamoDB storage"""
    if value is None:
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        logger.warning(f"Could not convert {value} to Decimal, using 0")
        return Decimal('0')

def ensure_device_exists_in_registry(device_id, device_metadata):
    """
    Ensure device exists in the device registry, create if it doesn't
    
    Args:
        device_id (str): Device ID to check/create
        device_metadata (dict): Device metadata from event
        
    Returns:
        dict: Device item (existing or newly created)
    """
    try:
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        
        # First try to find existing device by device_id (via GSI if available)
        device = get_device_by_id_from_registry(device_id)
        if device:
            logger.info(f"Device {device_id} found in registry")
            return device
        
        # Device doesn't exist, create it with metadata from the event
        logger.info(f"Device {device_id} not found. Creating new device entry.")
        
        # Generate a unique barcode if device_id is not suitable as primary key
        barcode = device_id if device_id.startswith('DEVICE-') else f"DEVICE-{device_id}"
        
        new_device = {
            'barcode': barcode,  # Primary key
            'device_id': device_id,  # GSI key
            'created_at': datetime.utcnow().isoformat(),
            'status': 'active',
            'device_type': device_metadata.get('device_type', 'iot_sensor'),
            'location': device_metadata.get('device_location', 'unknown'),
            'hostname': device_metadata.get('device_name', 'unknown'),
            'last_seen': datetime.utcnow().isoformat(),
            'TotalAnomalies': 0,
            'UpdatedAt': int(time.time()),
            'metadata': {
                'auto_created': True,
                'created_by': 'device_metadata_processor',
                'last_metadata_update': int(time.time())
            }
        }
        
        # Store the new device
        registry_table.put_item(Item=new_device)
        logger.info(f"Created new device entry for {device_id} with barcode {barcode}")
        
        return new_device
        
    except Exception as e:
        logger.error(f"Error ensuring device exists in registry: {str(e)}")
        return None

def get_device_by_id_from_registry(device_id):
    """
    Get device from DynamoDB registry using device_id (via GSI) or barcode (primary key)
    
    Args:
        device_id (str): Device ID to search for
        
    Returns:
        dict: Device item or None if not found
    """
    try:
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        
        # First try to get by device_id using GSI (if it exists)
        try:
            from boto3.dynamodb.conditions import Key
            response = registry_table.query(
                IndexName='DeviceIdIndex',  # Updated index name from CloudFormation
                KeyConditionExpression=Key('device_id').eq(device_id)
            )
            if response['Items']:
                logger.info(f"Found device via GSI: {device_id}")
                return response['Items'][0]
        except Exception as e:
            logger.warning(f"GSI query failed: {str(e)}")
        
        # If GSI fails, try direct lookup assuming device_id is the barcode
        try:
            response = registry_table.get_item(Key={'barcode': device_id})
            if 'Item' in response:
                logger.info(f"Found device via direct barcode lookup: {device_id}")
                return response['Item']
        except Exception as e:
            logger.warning(f"Direct barcode lookup failed: {str(e)}")
        
        logger.info(f"Device {device_id} not found in registry")
        return None
        
    except Exception as e:
        logger.error(f"Error getting device from registry: {str(e)}")
        return None

def store_device_metadata(device_id, device_metadata):
    """
    Store device metadata in the DeviceMetadata table
    
    Args:
        device_id (str): Device ID
        device_metadata (dict): Device metadata from EventBridge event
        
    Returns:
        bool: True if storage successful, False otherwise
    """
    try:
        metadata_table = dynamodb.Table(DEVICE_METADATA_TABLE)
        current_time = int(time.time())
        
        # Build device metadata record
        metadata_record = {
            'device_id': device_id,  # Partition key
            'last_updated': current_time,  # Sort key
            'device_location': device_metadata.get('device_location', 'unknown'),
            'device_name': device_metadata.get('device_name', 'unknown'),
            'device_type': device_metadata.get('device_type', 'iot_sensor'),
            'hostname': device_metadata.get('device_name', 'unknown'),
            'updated_at': current_time,
            'data_source': 'anomaly_detection_event',
            'metadata_version': '1.0'
        }
        
        # Add optional metadata fields if present
        optional_fields = ['firmware_version', 'ip_address', 'os_version', 'battery_level']
        for field in optional_fields:
            if field in device_metadata:
                metadata_record[field] = device_metadata[field]
        
        # Store the metadata record
        metadata_table.put_item(Item=metadata_record)
        logger.info(f"Stored device metadata for device {device_id}")
        return True

    except Exception as e:
        logger.error(f"Error storing device metadata: {str(e)}")
        return False

def update_device_last_seen(device_id):
    """
    Update the last_seen timestamp in the device registry
    
    Args:
        device_id (str): Device ID
        
    Returns:
        bool: True if update successful, False otherwise
    """
    try:
        # Get the device to find its barcode (primary key)
        device = get_device_by_id_from_registry(device_id)
        if not device:
            logger.warning(f"Could not find device {device_id} to update last_seen")
            return False
        
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        barcode = device['barcode']
        current_time = int(time.time())
        
        # Update the last_seen timestamp
        registry_table.update_item(
            Key={'barcode': barcode},
            UpdateExpression="SET last_seen = :time, UpdatedAt = :updated",
            ExpressionAttributeValues={
                ':time': datetime.utcnow().isoformat(),
                ':updated': current_time
            }
        )
        
        logger.info(f"Updated last_seen for device {device_id} (barcode: {barcode})")
        return True
    
    except Exception as e:
        logger.error(f"Error updating device last_seen: {str(e)}")
        return False

def lambda_handler(event, context):
    """
    AWS Lambda handler function for processing EventBridge events and storing device metadata only
    
    Args:
        event (dict): EventBridge event containing device metadata
        context (object): AWS Lambda context object
        
    Returns:
        dict: Response with status code and processing summary
    """
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Check if this is an anomaly event
        if event.get('detail-type') != 'AnomalyDetected':
            logger.info(f"Ignoring non-anomaly event: {event.get('detail-type')}")
            return {
                'statusCode': 200,
                'body': json.dumps('Event ignored - not an anomaly event')
            }
        
        # Extract event details
        detail = event.get('detail', {})
        device_id = detail.get('device_id')
        
        if not device_id:
            logger.error("Missing device_id in event")
            return {
                'statusCode': 400,
                'body': json.dumps('Missing device_id in event')
            }
        
        # Extract device metadata (NOT anomaly data)
        device_metadata = {
            'device_location': detail.get('device_location', 'unknown'),
            'device_name': detail.get('device_name', 'unknown'), 
            'device_type': detail.get('device_type', 'iot_sensor')
        }
        
        # Ensure device exists in registry
        device = ensure_device_exists_in_registry(device_id, device_metadata)
        if not device:
            logger.error(f"Could not ensure device {device_id} exists in registry")
            return {
                'statusCode': 500,
                'body': json.dumps('Failed to ensure device exists in registry')
            }
        
        # Store device metadata (location, name, type only)
        metadata_stored = store_device_metadata(device_id, device_metadata)
        
        # Update last seen timestamp in registry
        last_seen_updated = update_device_last_seen(device_id)
        
        if metadata_stored:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Successfully processed device metadata',
                    'device_id': device_id,
                    'device_location': device_metadata.get('device_location'),
                    'device_name': device_metadata.get('device_name'),
                    'device_type': device_metadata.get('device_type'),
                    'metadata_stored': metadata_stored,
                    'last_seen_updated': last_seen_updated,
                    'device_registry_updated': True
                }, default=decimal_default)
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Failed to store device metadata',
                    'device_id': device_id,
                    'metadata_stored': metadata_stored,
                    'last_seen_updated': last_seen_updated
                })
            }
    
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing device metadata: {str(e)}')
        }