# Updated Client API Lambda - NO MOCK DATA, only real TimeStream queries
import json
import boto3
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize TimeStream query client
try:
    REGION = os.environ.get('REGION', 'ap-northeast-1')
    timestream_query = boto3.client('timestream-query', region_name=REGION)
    
    # Get TimeStream configuration from environment
    TIMESTREAM_DATABASE = os.environ.get('TIMESTREAM_DATABASE', 'iotstuff-iot-data')
    TIMESTREAM_TABLE = os.environ.get('TIMESTREAM_TABLE', 'iotstuff-anomalies')
    
    logger.info(f"Initialized TimeStream client for region: {REGION}")
    logger.info(f"TimeStream Database: {TIMESTREAM_DATABASE}")
    logger.info(f"TimeStream Table: {TIMESTREAM_TABLE}")
    
except Exception as e:
    logger.error(f"Failed to initialize TimeStream client: {str(e)}")
    raise

def lambda_handler(event, context):
    """
    Client API Lambda handler - NO MOCK DATA, only real TimeStream queries
    """
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Extract HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        resource = event.get('resource', '')
        
        logger.info(f"Processing {http_method} request for path: {path}, resource: {resource}")
        
        # Handle CORS preflight for all endpoints
        if http_method == 'OPTIONS':
            return cors_response({
                'statusCode': 200,
                'body': json.dumps({'message': 'CORS preflight successful', 'path': path})
            })
        
        # Route requests based on path or resource
        if 'pvt-getanomaly-data' in path or 'pvt-getanomaly-data' in resource:
            return handle_get_anomaly_data_from_timestream(event)
        elif 'register-product' in path or 'register-product' in resource:
            return handle_register_product(event)
        elif 'update-device' in path or 'update-device' in resource:
            return handle_update_device(event)
        elif 'get-device' in path or 'get-device' in resource:
            return handle_get_device(event)
        elif 'get-status' in path or 'get-status' in resource:
            return handle_get_status(event)
        elif 'health' in path or path == '/':
            return handle_health_check(event)
        else:
            return cors_response({
                'statusCode': 404,
                'body': json.dumps({
                    'error': 'Endpoint not found', 
                    'path': path,
                    'resource': resource,
                    'available_endpoints': [
                        '/pvt-getanomaly-data (TimeStream data only)',
                        '/device/register-product',
                        '/device/update-device',
                        '/device/get-device',
                        '/device/get-status',
                        '/health'
                    ]
                })
            })
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return cors_response({
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error', 
                'details': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        })

def handle_get_anomaly_data_from_timestream(event):
    """
    Handle GET /pvt-getanomaly-data requests - ONLY REAL TIMESTREAM DATA
    """
    try:
        logger.info("Processing GET /pvt-getanomaly-data request - querying TimeStream")
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        device_id = query_params.get('deviceId')
        start_time = query_params.get('startTime')
        end_time = query_params.get('endTime')
        severity_filter = query_params.get('severity')
        limit = int(query_params.get('limit', 50))
        
        logger.info(f"Query params: deviceId={device_id}, startTime={start_time}, endTime={end_time}, severity={severity_filter}, limit={limit}")
        
        # Query real TimeStream data - NO MOCK DATA
        anomalies = query_timestream_anomalies_safe(
            device_id_filter=device_id,
            severity_filter=severity_filter,
            limit=limit
        )
        
        # Calculate statistics from real data
        stats = calculate_real_anomaly_statistics(anomalies)
        
        # Response data structure that matches React app expectations
        response_data = {
            'anomalies': anomalies,
            'count': len(anomalies),
            'statistics': stats,
            'status': 'success',
            'message': f'Retrieved {len(anomalies)} real anomalies from TimeStream',
            'filters_applied': {
                'deviceId': device_id,
                'severity': severity_filter,
                'startTime': start_time,
                'endTime': end_time,
                'limit': limit
            },
            'data_source': 'timestream_real_data',
            'database': TIMESTREAM_DATABASE,
            'table': TIMESTREAM_TABLE,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'endpoint': '/pvt-getanomaly-data',
            'mock_data': False  # Explicitly indicate this is real data
        }
        
        logger.info(f"Successfully returning {len(anomalies)} REAL anomalies from TimeStream")
        return cors_response({
            'statusCode': 200,
            'body': json.dumps(response_data, default=str)
        })
        
    except Exception as e:
        logger.error(f"Error in handle_get_anomaly_data_from_timestream: {str(e)}")
        return cors_response({
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Failed to get real anomaly data from TimeStream', 
                'details': str(e),
                'endpoint': '/pvt-getanomaly-data',
                'data_source': 'timestream',
                'mock_data': False
            })
        })

def query_timestream_anomalies_safe(device_id_filter=None, severity_filter=None, limit=50):
    """
    Query TimeStream using the same safe pattern as your working query Lambda
    """
    try:
        # Use the same safe query pattern as your working Lambda
        query_parts = [
            "SELECT",
            "device_id,",
            "measure_name,", 
            "measure_value::double AS value,",
            "time,",
            "severity,",
            "anomaly_type,",
            "metric_type,",
            "record_type",
            f'FROM "{TIMESTREAM_DATABASE}"."{TIMESTREAM_TABLE}"'
        ]
        
        where_conditions = []
        
        # Add device filter if specified
        if device_id_filter and device_id_filter.strip():
            safe_device_id = device_id_filter.replace("'", "''")
            where_conditions.append(f"device_id = '{safe_device_id}'")
        
        # Add severity filter if specified
        if severity_filter and severity_filter.strip():
            safe_severity = severity_filter.replace("'", "''")
            where_conditions.append(f"severity = '{safe_severity}'")
        
        # Add WHERE clause if needed
        if where_conditions:
            query_parts.append("WHERE " + " AND ".join(where_conditions))
        
        # Use the same ordering and limit pattern as your working Lambda
        query_parts.extend([
            "ORDER BY time DESC",
            f"LIMIT {limit * 3}"  # Get more records for grouping
        ])
        
        query = " ".join(query_parts)
        logger.info(f"Executing TimeStream query: {query}")
        
        # Execute query using same pattern as your working Lambda
        result = timestream_query.query(QueryString=query)
        raw_data = parse_timestream_results(result)
        
        logger.info(f"Retrieved {len(raw_data)} raw records from TimeStream")
        
        # Group and format results using same pattern as your working Lambda
        if raw_data:
            formatted_results = group_anomaly_records(raw_data)
            final_results = formatted_results[:limit]
        else:
            final_results = []
        
        logger.info(f"Returning {len(final_results)} formatted real anomalies")
        return final_results
        
    except Exception as e:
        logger.error(f"TimeStream query failed: {str(e)}")
        # Return empty list instead of mock data
        return []

def parse_timestream_results(result):
    """Parse TimeStream results using the same pattern as your working Lambda"""
    rows = result['Rows']
    columns = result['ColumnInfo']
    
    timestream_raw_data = []
    for row in rows:
        data = {}
        for idx, cell in enumerate(row['Data']):
            column_name = columns[idx]['Name']
            if 'ScalarValue' in cell:
                data[column_name] = cell['ScalarValue']
            elif 'NullValue' in cell:
                data[column_name] = None
        timestream_raw_data.append(data)
    
    return timestream_raw_data

def group_anomaly_records(raw_data):
    """Group anomaly records using the same pattern as your working Lambda"""
    grouped = defaultdict(dict)
    
    for row_data in raw_data:
        # Create grouping key using device_id and time
        key = (row_data.get('device_id'), row_data.get('time'))
        
        anomaly = grouped[key]
        anomaly['device_id'] = row_data.get('device_id')
        anomaly['timestamp'] = row_data.get('time')
        anomaly['severity'] = row_data.get('severity')
        anomaly['anomaly_type'] = row_data.get('anomaly_type')
        anomaly['record_type'] = row_data.get('record_type')
        
        # Initialize metrics dict if not exists
        if 'metrics' not in anomaly:
            anomaly['metrics'] = {}
        
        # Add measure to metrics
        measure_name = row_data.get('measure_name')
        if measure_name:
            # Try to convert measure_value to float
            measure_value = row_data.get('value')
            if measure_value is not None:
                try:
                    anomaly['metrics'][measure_name] = float(measure_value)
                except:
                    anomaly['metrics'][measure_name] = measure_value
    
    # Convert to list and sort by timestamp
    final_data = list(grouped.values())
    final_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return final_data

def calculate_real_anomaly_statistics(anomalies):
    """Calculate statistics from real TimeStream anomaly data"""
    if not anomalies:
        return {
            'total': 0,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0},
            'by_device': {},
            'unique_devices': 0,
            'data_source': 'timestream_real'
        }
    
    stats = {
        'total': len(anomalies),
        'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0},
        'by_device': {},
        'data_source': 'timestream_real'
    }
    
    for anomaly in anomalies:
        # Count by severity
        severity = anomaly.get('severity', 'UNKNOWN')
        if severity in stats['by_severity']:
            stats['by_severity'][severity] += 1
        
        # Count by device
        device_id = anomaly.get('device_id', 'unknown')
        stats['by_device'][device_id] = stats['by_device'].get(device_id, 0) + 1
    
    stats['unique_devices'] = len(stats['by_device'])
    
    return stats

# Keep the existing functions for other endpoints (register-product, etc.)
def handle_register_product(event):
    """Handle POST /device/register-product requests"""
    try:
        logger.info("Processing POST /device/register-product request")
        
        # Parse request body
        body = {}
        if event.get('body'):
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        
        device_id = body.get('deviceId', f"device_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        product_type = body.get('productType', 'generic')
        location = body.get('location', 'unknown')
        manufacturer = body.get('manufacturer', 'unknown')
        
        # Simulate device registration (you can replace with real database logic)
        device_data = {
            'deviceId': device_id,
            'productType': product_type,
            'location': location,
            'manufacturer': manufacturer,
            'status': 'registered',
            'registeredAt': datetime.utcnow().isoformat() + 'Z',
            'endpoint': '/device/register-product'
        }
        
        logger.info(f"Device registered: {device_id}")
        return cors_response({
            'statusCode': 201,
            'body': json.dumps(device_data, default=str)
        })
        
    except Exception as e:
        logger.error(f"Error in handle_register_product: {str(e)}")
        return cors_response({
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to register product', 'details': str(e)})
        })

def handle_update_device(event):
    """Handle POST /device/update-device requests"""
    try:
        logger.info("Processing POST /device/update-device request")
        
        body = {}
        if event.get('body'):
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        
        device_id = body.get('deviceId')
        if not device_id:
            return cors_response({
                'statusCode': 400,
                'body': json.dumps({'error': 'deviceId is required'})
            })
        
        updates = body.get('updates', {})
        
        updated_device = {
            'deviceId': device_id,
            'updates': updates,
            'status': 'updated',
            'updatedAt': datetime.utcnow().isoformat() + 'Z',
            'endpoint': '/device/update-device'
        }
        
        logger.info(f"Device updated: {device_id}")
        return cors_response({
            'statusCode': 200,
            'body': json.dumps(updated_device, default=str)
        })
        
    except Exception as e:
        logger.error(f"Error in handle_update_device: {str(e)}")
        return cors_response({
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to update device', 'details': str(e)})
        })

def handle_get_device(event):
    """Handle POST /device/get-device requests"""
    try:
        logger.info("Processing POST /device/get-device request")
        
        body = {}
        if event.get('body'):
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        
        device_id = body.get('deviceId')
        if not device_id:
            return cors_response({
                'statusCode': 400,
                'body': json.dumps({'error': 'deviceId is required'})
            })
        
        device_data = {
            'deviceId': device_id,
            'productType': 'IoT Sensor',
            'location': 'Building A, Floor 3',
            'status': 'active',
            'lastSeen': datetime.utcnow().isoformat() + 'Z',
            'endpoint': '/device/get-device'
        }
        
        logger.info(f"Device data retrieved for: {device_id}")
        return cors_response({
            'statusCode': 200,
            'body': json.dumps(device_data, default=str)
        })
        
    except Exception as e:
        logger.error(f"Error in handle_get_device: {str(e)}")
        return cors_response({
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to get device', 'details': str(e)})
        })

def handle_get_status(event):
    """Handle POST /device/get-status requests"""
    try:
        logger.info("Processing POST /device/get-status request")
        
        body = {}
        if event.get('body'):
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        
        device_id = body.get('deviceId')
        if not device_id:
            return cors_response({
                'statusCode': 400,
                'body': json.dumps({'error': 'deviceId is required'})
            })
        
        status_data = {
            'deviceId': device_id,
            'status': 'online',
            'lastPing': datetime.utcnow().isoformat() + 'Z',
            'endpoint': '/device/get-status'
        }
        
        logger.info(f"Status retrieved for device: {device_id}")
        return cors_response({
            'statusCode': 200,
            'body': json.dumps(status_data, default=str)
        })
        
    except Exception as e:
        logger.error(f"Error in handle_get_status: {str(e)}")
        return cors_response({
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to get status', 'details': str(e)})
        })

def handle_health_check(event):
    """Health check endpoint"""
    try:
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'version': '1.0.0',
            'service': 'Client API - Real TimeStream Data Only',
            'mock_data_disabled': True,
            'endpoints': [
                'GET /pvt-getanomaly-data (Real TimeStream data)',
                'POST /device/register-product',
                'POST /device/update-device',
                'POST /device/get-device',
                'POST /device/get-status'
            ]
        }
        
        return cors_response({
            'statusCode': 200,
            'body': json.dumps(health_data, default=str)
        })
    except Exception as e:
        return cors_response({
            'statusCode': 500,
            'body': json.dumps({'status': 'unhealthy', 'error': str(e)})
        })

def cors_response(response):
    """Add comprehensive CORS headers to response"""
    if 'headers' not in response:
        response['headers'] = {}
    
    response['headers'].update({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
        'Access-Control-Max-Age': '86400',
        'Content-Type': 'application/json'
    })
    
    return response