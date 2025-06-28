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
REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)

# Environment configuration
DEVICE_REGISTRY_TABLE = os.environ.get('DEVICE_REGISTRY_TABLE')
ANOMALY_EVENTS_TABLE = os.environ.get('ANOMALY_EVENTS_TABLE')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serializable')

def lambda_handler(event, context):
    """
    Get extended device metadata and anomaly gallery URL
    Returns comprehensive device information with anomaly analysis
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

        # Get device metadata from registry table
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        
        try:
            # Try to get by device_id using GSI
            response = registry_table.query(
                IndexName='device-id-index',
                KeyConditionExpression='device_id = :device_id',
                ExpressionAttributeValues={':device_id': device_id}
            )
            
            device = None
            if response['Items']:
                device = response['Items'][0]
            else:
                # If not found by device_id, try by barcode (primary key)
                response = registry_table.get_item(
                    Key={'barcode': device_id}
                )
                
                if 'Item' in response:
                    device = response['Item']

            if not device:
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': 'No metadata found for device'})
                }

            # Get comprehensive anomaly analysis
            anomaly_table = dynamodb.Table(ANOMALY_EVENTS_TABLE)
            
            import time
            from datetime import datetime, timedelta
            
            current_time = int(time.time())
            week_ago = current_time - (7 * 24 * 60 * 60)  # 7 days ago
            
            anomaly_status = "No anomalies detected"
            anomaly_summary = {
                'total_anomalies': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'latest_anomaly': None,
                'most_common_methods': []
            }
            
            try:
                # Get anomalies from the last week for comprehensive analysis
                anomaly_response = anomaly_table.query(
                    KeyConditionExpression='device_id = :device_id AND #ts > :week_ago',
                    ExpressionAttributeNames={'#ts': 'timestamp'},
                    ExpressionAttributeValues={
                        ':device_id': device_id,
                        ':week_ago': week_ago
                    },
                    ScanIndexForward=False,  # Get most recent first
                    Limit=100  # Limit to last 100 anomalies for analysis
                )
                
                anomalies = anomaly_response['Items']
                anomaly_summary['total_anomalies'] = len(anomalies)
                
                if anomalies:
                    # Analyze anomaly severity and methods
                    method_counts = {}
                    severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
                    
                    latest_anomaly = anomalies[0]  # Most recent
                    
                    for anomaly in anomalies:
                        # Count methods
                        methods = anomaly.get('anomaly_methods', [])
                        for method in methods:
                            method_counts[method] = method_counts.get(method, 0) + 1
                        
                        # Classify severity based on method count and values
                        anomaly_count = anomaly.get('anomaly_count', 0)
                        z_score = anomaly.get('z_score', 0)
                        
                        if anomaly_count >= 4 or z_score > 4:
                            severity_counts['critical'] += 1
                        elif anomaly_count >= 3 or z_score > 3:
                            severity_counts['high'] += 1
                        elif anomaly_count >= 2 or z_score > 2:
                            severity_counts['medium'] += 1
                        else:
                            severity_counts['low'] += 1
                    
                    # Update summary
                    anomaly_summary.update({
                        'critical_count': severity_counts['critical'],
                        'high_count': severity_counts['high'],
                        'medium_count': severity_counts['medium'],
                        'low_count': severity_counts['low'],
                        'latest_anomaly': {
                            'timestamp': latest_anomaly.get('timestamp'),
                            'cpu_usage': latest_anomaly.get('cpu_usage'),
                            'methods': latest_anomaly.get('anomaly_methods', []),
                            'z_score': latest_anomaly.get('z_score')
                        },
                        'most_common_methods': sorted(method_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                    })
                    
                    # Determine overall status
                    if severity_counts['critical'] > 0:
                        anomaly_status = f"Critical anomalies detected ({severity_counts['critical']} critical, {len(anomalies)} total)"
                    elif severity_counts['high'] > 5:
                        anomaly_status = f"High anomaly activity ({severity_counts['high']} high severity events)"
                    elif len(anomalies) > 20:
                        anomaly_status = f"Frequent anomalies detected ({len(anomalies)} events in last week)"
                    elif len(anomalies) > 0:
                        anomaly_status = f"Some anomalies detected ({len(anomalies)} events in last week)"
                        
            except Exception as e:
                logger.warning(f"Could not perform anomaly analysis: {e}")
                # Continue with default status

            # Generate gallery URL using the Amplify app domain
            # Note: Replace with your actual Amplify domain after deployment
            amplify_domain = os.environ.get('AMPLIFY_DOMAIN', 'master.d1foo8stljrhaq.amplifyapp.com')
            gallery_url = f"https://{amplify_domain}/device/{device_id}/gallery"

            # Build comprehensive response
            response_data = {
                'productAnomalyStatus': anomaly_status,
                'graphUrl': gallery_url,
                'barcode': device.get('barcode', device_id),
                'productName': device.get('productName', device.get('product_name', 'Unknown Product')),
                'modelNo': device.get('modelNo', device.get('model_no', 'Unknown Model')),
                'serialNo': device.get('serialNo', device.get('serial_no', 'Unknown Serial')),
                'manufacturerName': device.get('manufacturerName', device.get('manufacturer_name', 'Unknown Manufacturer')),
                
                # Extended metadata
                'device_id': device.get('device_id', device_id),
                'anomaly_summary': anomaly_summary,
                
                # Optional device fields
                'manufacturerId': device.get('manufacturerId'),
                'vendorId': device.get('vendorId'),
                'buyerId': device.get('buyerId'),
                'location': device.get('location'),
                'type': device.get('type'),
                'registeredAt': device.get('registeredAt'),
                'lastUpdated': device.get('lastUpdated')
            }
            
            # Remove None values for cleaner response
            response_data = {k: v for k, v in response_data.items() if v is not None}

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(response_data, default=decimal_default)
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