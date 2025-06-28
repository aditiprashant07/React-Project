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
DEVICE_REGISTRY_TABLE = os.environ.get('DEVICE_REGISTRY_TABLE')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serializable')

def build_update_expression(update_data):
    """
    Build DynamoDB update expression from provided data
    
    Args:
        update_data (dict): Data to update
        
    Returns:
        tuple: (update_expression, expression_attribute_values, expression_attribute_names)
    """
    # Fields that can be updated
    updatable_fields = {
        'productName': 'productName',
        'modelNo': 'modelNo', 
        'serialNo': 'serialNo',
        'manufacturerName': 'manufacturerName',
        'manufacturerId': 'manufacturerId',
        'vendorId': 'vendorId',
        'buyerId': 'buyerId',
        'location': 'location',
        'type': 'type',
        'description': 'description',
        'firmware_version': 'firmware_version',
        'status': 'status'
    }
    
    set_clauses = []
    expression_values = {}
    expression_names = {}
    
    for field, db_field in updatable_fields.items():
        if field in update_data and update_data[field] is not None:
            # Handle reserved keywords by using expression attribute names
            if db_field in ['type', 'status']:
                name_placeholder = f"#{db_field}"
                value_placeholder = f":{db_field}"
                expression_names[name_placeholder] = db_field
                set_clauses.append(f"{name_placeholder} = {value_placeholder}")
            else:
                value_placeholder = f":{db_field}"
                set_clauses.append(f"{db_field} = {value_placeholder}")
            
            expression_values[value_placeholder] = update_data[field]
    
    # Always update the lastUpdated timestamp
    set_clauses.append("lastUpdated = :lastUpdated")
    expression_values[":lastUpdated"] = int(time.time())
    
    if not set_clauses:
        return None, None, None
    
    update_expression = "SET " + ", ".join(set_clauses)
    
    return update_expression, expression_values, expression_names if expression_names else None

def lambda_handler(event, context):
    """
    Update device information in the device registry table
    Only updates provided fields, requires barcode as identifier
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

        # Validate required barcode field
        if 'barcode' not in body or not body['barcode']:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Missing \'barcode\''})
            }

        barcode = body['barcode']
        
        # Remove barcode from update data since it's the key
        update_data = {k: v for k, v in body.items() if k != 'barcode'}
        
        if not update_data:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'No fields to update'})
            }

        # Build update expression
        update_expression, expression_values, expression_names = build_update_expression(update_data)
        
        if not update_expression:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'No valid fields to update'})
            }

        # Update device in registry table
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        
        try:
            # First check if device exists
            existing_device = registry_table.get_item(
                Key={'barcode': barcode}
            )
            
            if 'Item' not in existing_device:
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': 'Device not found'})
                }

            # Perform the update
            update_params = {
                'Key': {'barcode': barcode},
                'UpdateExpression': update_expression,
                'ExpressionAttributeValues': expression_values,
                'ReturnValues': 'ALL_NEW'
            }
            
            if expression_names:
                update_params['ExpressionAttributeNames'] = expression_names

            response = registry_table.update_item(**update_params)
            
            # Prepare response
            updated_item = response['Attributes']
            
            response_data = {
                'message': 'Device updated successfully',
                'barcode': barcode,
                'device_id': updated_item.get('device_id', barcode),
                'lastUpdated': updated_item.get('lastUpdated'),
                'updated_fields': list(update_data.keys())
            }
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(response_data, default=decimal_default)
            }

        except ClientError as e:
            logger.error(f"DynamoDB error during update: {e}")
            
            error_code = e.response['Error']['Code']
            if error_code == 'ValidationException':
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Invalid update data provided'})
                }
            elif error_code == 'ResourceNotFoundException':
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': 'Device not found'})
                }
            else:
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps({'error': 'Update failed - database error'})
                }

    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Detailed error message'})
        }