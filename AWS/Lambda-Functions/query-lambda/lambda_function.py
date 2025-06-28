import json
import boto3
import os
import logging
from datetime import datetime
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

REGION = os.environ.get('REGION', os.environ.get('AWS_REGION', 'ap-northeast-1'))

# Initialize Timestream query client
try:
    timestream_query = boto3.client('timestream-query', region_name=REGION)
    logger.info("Timestream query client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Timestream client: {str(e)}")
    raise

# Environment variables
TIMESTREAM_DATABASE = os.environ.get('TIMESTREAM_DATABASE', 'iotdata')
TIMESTREAM_TABLE = os.environ.get('TIMESTREAM_TABLE', 'iotstuff-anomalies')

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
            measure_value = row_data.get('measure_value::double') or row_data.get('value')
            if measure_value is not None:
                try:
                    anomaly['metrics'][measure_name] = float(measure_value)
                except:
                    anomaly['metrics'][measure_name] = measure_value
    
    # Convert to list and sort by timestamp
    final_data = list(grouped.values())
    final_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return final_data

def query_anomalies_no_time_filter(device_id=None, limit=100, format_type='grouped'):
    """
    Query anomalies using the SAME PATTERN as your working Lambda - NO TIME FILTERS
    """
    try:
        # Validate inputs
        limit = max(1, min(int(limit), 1000))
        
        # Build query using the EXACT same pattern as your working Lambda
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
        if device_id and device_id.strip():
            safe_device_id = device_id.replace("'", "''")
            where_conditions.append(f"device_id = '{safe_device_id}'")
        
        # Add WHERE clause if needed
        if where_conditions:
            query_parts.append("WHERE " + " AND ".join(where_conditions))
        
        # CRITICAL: Use the same ordering and limit pattern as your working Lambda
        query_parts.extend([
            "ORDER BY time DESC",
            f"LIMIT {limit * 3}"  # Get more records for grouping
        ])
        
        query = " ".join(query_parts)
        logger.info(f"Executing query (no time filter): {query}")
        
        # Execute query using same pattern
        result = timestream_query.query(QueryString=query)
        raw_data = parse_timestream_results(result)
        
        logger.info(f"Retrieved {len(raw_data)} raw records")
        
        # Format results
        if format_type == 'grouped' and raw_data:
            formatted_results = group_anomaly_records(raw_data)
            final_results = formatted_results[:limit]
        else:
            final_results = raw_data[:limit]
        
        logger.info(f"Returning {len(final_results)} formatted records")
        return final_results
        
    except Exception as e:
        logger.error(f"Query failed: {str(e)}")
        raise

def query_anomalies_with_ago(device_id=None, hours=24, limit=100, format_type='grouped'):
    """
    Alternative query method using ago() function for time filtering
    """
    try:
        # Validate inputs
        hours = max(1, min(int(hours), 168))
        limit = max(1, min(int(limit), 1000))
        
        # Build query with ago() function
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
            f'FROM "{TIMESTREAM_DATABASE}"."{TIMESTREAM_TABLE}"',
            f"WHERE time >= ago({hours}h)"
        ]
        
        # Add device filter if specified
        if device_id and device_id.strip():
            safe_device_id = device_id.replace("'", "''")
            query_parts.append(f"AND device_id = '{safe_device_id}'")
        
        query_parts.extend([
            "ORDER BY time DESC",
            f"LIMIT {limit * 3}"
        ])
        
        query = " ".join(query_parts)
        logger.info(f"Executing query with ago({hours}h): {query}")
        
        result = timestream_query.query(QueryString=query)
        raw_data = parse_timestream_results(result)
        
        logger.info(f"Retrieved {len(raw_data)} raw records")
        
        # Format results
        if format_type == 'grouped' and raw_data:
            formatted_results = group_anomaly_records(raw_data)
            final_results = formatted_results[:limit]
        else:
            final_results = raw_data[:limit]
        
        logger.info(f"Returning {len(final_results)} formatted records")
        return final_results
        
    except Exception as e:
        logger.error(f"Query with ago() failed: {str(e)}")
        # Fallback to no time filter
        logger.info("Falling back to query without time filter")
        return query_anomalies_no_time_filter(device_id, limit, format_type)

def get_summary_safe(device_id=None, limit=1000):
    """Get summary statistics using safe query pattern"""
    try:
        # Use the same safe pattern as your working Lambda
        query_parts = [
            "SELECT",
            "device_id,",
            "measure_name,", 
            "measure_value::double AS value,",
            "time,",
            "severity",
            f'FROM "{TIMESTREAM_DATABASE}"."{TIMESTREAM_TABLE}"'
        ]
        
        if device_id and device_id.strip():
            safe_device_id = device_id.replace("'", "''")
            query_parts.append(f"WHERE device_id = '{safe_device_id}'")
        
        query_parts.extend([
            "ORDER BY time DESC",
            f"LIMIT {limit}"
        ])
        
        query = " ".join(query_parts)
        logger.info(f"Executing summary query: {query}")
        
        result = timestream_query.query(QueryString=query)
        raw_data = parse_timestream_results(result)
        
        # Calculate statistics
        unique_devices = len(set(row.get('device_id') for row in raw_data if row.get('device_id')))
        
        # Group by device and time to count events
        grouped = defaultdict(set)
        for row in raw_data:
            device = row.get('device_id')
            timestamp = row.get('time', '')[:16]  # Group by minute
            if device and timestamp:
                grouped[device].add(timestamp)
        
        total_events = sum(len(timestamps) for timestamps in grouped.values())
        
        # Count by severity
        severity_counts = defaultdict(int)
        for row in raw_data:
            severity = row.get('severity')
            if severity:
                severity_counts[severity] += 1
        
        return {
            'total_records': len(raw_data),
            'unique_devices': unique_devices,
            'estimated_events': total_events,
            'severity_breakdown': dict(severity_counts)
        }
        
    except Exception as e:
        logger.error(f"Summary query failed: {str(e)}")
        return {'error': str(e)}

def get_devices_safe():
    """Get device list using safe query pattern"""
    try:
        query = f'''
        SELECT DISTINCT device_id 
        FROM "{TIMESTREAM_DATABASE}"."{TIMESTREAM_TABLE}"
        ORDER BY device_id
        LIMIT 100
        '''
        
        result = timestream_query.query(QueryString=query)
        raw_data = parse_timestream_results(result)
        
        devices = [row.get('device_id') for row in raw_data if row.get('device_id')]
        return devices
        
    except Exception as e:
        logger.error(f"Device list query failed: {str(e)}")
        return []

def lambda_handler(event, context):
    """
    Lambda handler using the SAME SAFE PATTERNS as your working Lambda
    """
    
    headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent,X-Requested-With,Accept,Accept-Language,Content-Language,Cache-Control,Pragma',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
    'Access-Control-Allow-Credentials': 'false',
    'Access-Control-Max-Age': '86400'
    }
    
    try:
        # Handle CORS
        if event.get('httpMethod') == 'OPTIONS':
            return {'statusCode': 200, 'headers': headers, 'body': ''}
        
        # Parse request body safely
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except:
                logger.warning("Could not parse JSON body")
        
        # Parse query parameters safely
        query_params = event.get('queryStringParameters') or {}
        for key, value in query_params.items():
            if key in ['hours', 'limit']:
                try:
                    body[key] = int(value)
                except:
                    pass
            else:
                body[key] = value
        
        # Extract parameters with safe defaults
        operation = body.get('operation', 'query_anomalies')
        device_id = body.get('device_id')
        hours = body.get('hours', 24)
        limit = body.get('limit', 100)
        format_type = body.get('format', 'grouped')
        use_time_filter = body.get('use_time_filter', True)  # Allow disabling time filter
        
        logger.info(f"Processing {operation} - device:{device_id}, hours:{hours}, use_time_filter:{use_time_filter}")
        
        # Handle operations
        if operation == 'summary':
            summary_data = get_summary_safe(device_id, limit * 10)
            result = {
                'operation': 'summary',
                'device_id': device_id,
                'summary': summary_data,
                'timestamp': datetime.now().isoformat()
            }
            
        elif operation == 'devices':
            device_list = get_devices_safe()
            result = {
                'operation': 'devices',
                'devices': device_list,
                'device_count': len(device_list),
                'timestamp': datetime.now().isoformat()
            }
            
        else:  # query_anomalies (default)
            # Try time filter first, fall back to no filter if it fails
            if use_time_filter:
                try:
                    anomalies = query_anomalies_with_ago(device_id, hours, limit, format_type)
                except:
                    logger.warning("Time filter failed, using no time filter")
                    anomalies = query_anomalies_no_time_filter(device_id, limit, format_type)
            else:
                anomalies = query_anomalies_no_time_filter(device_id, limit, format_type)
            
            result = {
                'operation': 'query_anomalies',
                'device_id': device_id,
                'anomalies': anomalies,
                'count': len(anomalies),
                'format': format_type,
                'hours': hours if use_time_filter else None,
                'timestamp': datetime.now().isoformat()
            }
        
        logger.info(f"Operation {operation} completed successfully")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        logger.error(f"Lambda error: {str(e)}")
        
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': str(e),
                'operation': body.get('operation', 'unknown') if 'body' in locals() else 'unknown',
                'timestamp': datetime.now().isoformat()
            })
        }

# Test function for local debugging
def test_locally():
    """Test the functions locally using safe patterns"""
    print("🧪 Testing safe Lambda locally...")
    
    test_events = [
        {
            'name': 'No Time Filter Query',
            'body': json.dumps({
                'operation': 'query_anomalies',
                'limit': 5,
                'use_time_filter': False
            })
        },
        {
            'name': 'With Time Filter Query',
            'body': json.dumps({
                'operation': 'query_anomalies',
                'hours': 24,
                'limit': 5,
                'use_time_filter': True
            })
        },
        {
            'name': 'Summary',
            'body': json.dumps({
                'operation': 'summary'
            })
        },
        {
            'name': 'Devices',
            'body': json.dumps({
                'operation': 'devices'
            })
        }
    ]
    
    for test_case in test_events:
        print(f"\n🧪 Testing: {test_case['name']}")
        try:
            result = lambda_handler({'body': test_case['body']}, None)
            print(f"Status: {result['statusCode']}")
            if result['statusCode'] == 200:
                body = json.loads(result['body'])
                operation = body.get('operation')
                count = body.get('count', body.get('device_count', 'N/A'))
                print(f"Operation: {operation}, Count: {count}")
            else:
                print(f"Error: {result['body']}")
        except Exception as e:
            print(f"Exception: {str(e)}")

if __name__ == "__main__":
    test_locally()