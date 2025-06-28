import json
import boto3
import time
from datetime import datetime
import logging
import os
import re
from decimal import Decimal

# Configure logging for CloudWatch
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Initialize AWS clients
try:
    REGION = os.environ.get('REGION', 'ap-northeast-1')
    timestream = boto3.client('timestream-write', region_name=REGION)
    logger.info("AWS clients initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AWS clients: {str(e)}")
    raise

# Configuration from environment variables
TIMESTREAM_DATABASE_RAW = os.environ.get('TIMESTREAM_DATABASE', 'iotdata')
TIMESTREAM_TABLE_RAW = os.environ.get('TIMESTREAM_TABLE', 'iotanomalies')

def sanitize_timestream_name(name):
    """Sanitize TimeStream names to match pattern [a-zA-Z0-9_.-]+"""
    if not name: return 'default_name'
    sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '_', str(name))
    if sanitized and sanitized[0].isdigit(): sanitized = f"ts_{sanitized}"
    if len(sanitized) < 3: sanitized = f"{sanitized}_tbl"
    return sanitized

TIMESTREAM_DATABASE = sanitize_timestream_name(TIMESTREAM_DATABASE_RAW)
TIMESTREAM_TABLE = sanitize_timestream_name(TIMESTREAM_TABLE_RAW)
logger.info(f"Using sanitized TimeStream DB: '{TIMESTREAM_DATABASE}', Table: '{TIMESTREAM_TABLE}'")

def write_anomaly_to_timestream(device_id, anomaly_data):
    """
    Writes a single, comprehensive multi-measure record to Amazon Timestream.
    This record contains all anomaly metrics and the full data window.
    """
    try:
        # Use provided timestamp or current time
        timestamp = int(anomaly_data.get('timestamp', time.time()))
        anomaly_time_ms_str = str(timestamp * 1000)
        logger.info(f"Using timestamp: {datetime.fromtimestamp(timestamp)}")

        # --- Build Dimensions for powerful filtering ---
        dimensions = [
            {'Name': 'device_id', 'Value': device_id},
            {'Name': 'severity', 'Value': anomaly_data.get('severity', 'UNKNOWN')},
            {'Name': 'anomaly_type', 'Value': anomaly_data.get('anomaly_type', 'cpu_usage')},
            {'Name': 'method_count', 'Value': str(anomaly_data.get('method_count', 0))},
            # Storing triggered methods as a comma-separated string for easy LIKE queries
            {'Name': 'methods_triggered', 'Value': ",".join(anomaly_data.get('methods_triggered', []))}
        ]

        # --- Build the list of Measures for the MULTI record ---
        multi_measures = [
            # The core anomalous value
            {'Name': 'cpu_value', 'Value': str(anomaly_data.get('value', 0)), 'Type': 'DOUBLE'},
            # All detection scores
            {'Name': 'z_score', 'Value': str(anomaly_data.get('z_score', 0)), 'Type': 'DOUBLE'},
            {'Name': 'ewma_score', 'Value': str(anomaly_data.get('ewma_score', 0)), 'Type': 'DOUBLE'},
            {'Name': 'rate_of_change', 'Value': str(anomaly_data.get('rate_of_change', 0)), 'Type': 'DOUBLE'},
            {'Name': 'hampel_score', 'Value': '1.0' if anomaly_data.get('hampel_score') else '0.0', 'Type': 'DOUBLE'},
            # Contextual statistics
            {'Name': 'cpu_mean', 'Value': str(anomaly_data.get('cpu_mean', 0)), 'Type': 'DOUBLE'},
            {'Name': 'cpu_std', 'Value': str(anomaly_data.get('cpu_std', 1.0)), 'Type': 'DOUBLE'},
            # *** NEW: The full data window as a JSON string ***
            {'Name': 'context_window_json', 'Value': json.dumps(anomaly_data.get('cpu_window', [])), 'Type': 'VARCHAR'}
        ]

        # --- Assemble the single multi-measure record ---
        record = {
            'Dimensions': dimensions,
            'MeasureName': 'anomaly_event',  # A common name for the multi-measure record
            'MeasureValues': multi_measures,
            'MeasureValueType': 'MULTI',
            'Time': anomaly_time_ms_str,
            'TimeUnit': 'MILLISECONDS'
        }
        
        response = timestream.write_records(
            DatabaseName=TIMESTREAM_DATABASE,
            TableName=TIMESTREAM_TABLE,
            Records=[record] # Note: We are now only sending a list with ONE record
        )
        
        logger.info(f"Successfully wrote 1 multi-measure anomaly record to TimeStream for device {device_id}")
        return response
        
    except timestream.exceptions.RejectedRecordsException as e:
        logger.error(f"TimeStream rejected records: {e}")
        for rejected in e.response.get('RejectedRecords', []):
            logger.error(f"Rejected record index {rejected.get('RecordIndex')}: {rejected.get('Reason')}")
        raise
    except Exception as e:
        logger.error(f"Failed to write to TimeStream: {str(e)}")
        raise

def verify_and_create_resources(database_name, table_name):
    """Verify TimeStream resources exist, creating them if necessary."""
    try:
        timestream.describe_database(DatabaseName=database_name)
    except timestream.exceptions.ResourceNotFoundException:
        logger.warning(f"Database '{database_name}' not found. Creating.")
        try:
            timestream.create_database(DatabaseName=database_name)
            logger.info(f"Created database: {database_name}")
            time.sleep(1)
        except timestream.exceptions.ConflictException: pass # Race condition
        except Exception as e:
            logger.error(f"Failed to create database: {e}"); return False

    try:
        timestream.describe_table(DatabaseName=database_name, TableName=table_name)
    except timestream.exceptions.ResourceNotFoundException:
        logger.warning(f"Table '{table_name}' not found. Creating.")
        try:
            retention = {'MemoryStoreRetentionPeriodInHours': 24, 'MagneticStoreRetentionPeriodInDays': 7}
            timestream.create_table(DatabaseName=database_name, TableName=table_name, RetentionProperties=retention)
            logger.info(f"Created table: {table_name}. Waiting for it to become ACTIVE...")
            # Wait for table to become active
            waiter = timestream.get_waiter('table_exists')
            waiter.wait(DatabaseName=database_name, TableName=table_name)
            logger.info("Table is now ACTIVE.")
        except timestream.exceptions.ConflictException: pass # Race condition
        except Exception as e:
            logger.error(f"Failed to create or wait for table: {e}"); return False
    return True

def lambda_handler(event, context):
    """Processes 'AnomalyDetected' events and stores a single comprehensive record in TimeStream."""
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        if event.get('detail-type') != 'AnomalyDetected':
            return {'statusCode': 200, 'body': json.dumps('Event ignored')}
        
        detail = event.get('detail', {})
        device_id = detail.get('device_id')
        if not device_id:
            logger.error("Missing 'device_id' in event detail")
            return {'statusCode': 400, 'body': json.dumps('Missing device_id')}
        
        if not verify_and_create_resources(TIMESTREAM_DATABASE, TIMESTREAM_TABLE):
             return {'statusCode': 500, 'body': json.dumps('Failed to verify/create TimeStream resources')}
        
        write_anomaly_to_timestream(device_id, detail)
            
        return {'statusCode': 200, 'body': json.dumps({
                    'message': 'Successfully processed anomaly and wrote to TimeStream',
                    'device_id': device_id
                })}
            
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps(f'Error processing anomaly data: {str(e)}')}