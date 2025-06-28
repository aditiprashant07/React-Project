import json
import boto3
import os
import logging
from datetime import datetime
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize AWS clients
REGION = os.environ.get('REGION', 'ap-northeast-1')
sns = boto3.client('sns', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)

# Environment configuration
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
DEVICE_REGISTRY_TABLE = os.environ.get('DEVICE_REGISTRY_TABLE', 'DeviceRegistration')
NOTIFICATION_THRESHOLD = os.environ.get('NOTIFICATION_THRESHOLD', 'MEDIUM')

def get_device_info(device_id):
    """
    Get device information from registry for enriched notifications
    
    Args:
        device_id (str): Device ID
        
    Returns:
        dict: Device information or None if not found
    """
    try:
        registry_table = dynamodb.Table(DEVICE_REGISTRY_TABLE)
        
        # Try to get by device_id using GSI
        try:
            from boto3.dynamodb.conditions import Key
            response = registry_table.query(
                IndexName='DeviceIdIndex',
                KeyConditionExpression=Key('device_id').eq(device_id)
            )
            if response['Items']:
                return response['Items'][0]
        except Exception as e:
            logger.warning(f"GSI query failed: {str(e)}")
        
        # Try direct lookup by barcode
        try:
            response = registry_table.get_item(Key={'barcode': device_id})
            if 'Item' in response:
                return response['Item']
        except Exception as e:
            logger.warning(f"Direct lookup failed: {str(e)}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting device info: {str(e)}")
        return None

def should_send_notification(severity, threshold):
    """
    Determine if notification should be sent based on severity and threshold
    
    Args:
        severity (str): Anomaly severity level
        threshold (str): Configured notification threshold
        
    Returns:
        bool: True if notification should be sent
    """
    severity_levels = {
        'LOW': 1,
        'MEDIUM': 2,
        'HIGH': 3,
        'CRITICAL': 4
    }
    
    severity_value = severity_levels.get(severity.upper(), 0)
    threshold_value = severity_levels.get(threshold.upper(), 2)  # Default to MEDIUM
    
    return severity_value >= threshold_value

def format_notification_message(device_id, anomaly_data, device_info=None):
    """
    Format comprehensive notification message with all EventBridge data
    
    Args:
        device_id (str): Device ID
        anomaly_data (dict): Complete anomaly data from EventBridge
        device_info (dict): Device registration information
        
    Returns:
        tuple: (subject, message)
    """
    # Extract key anomaly information
    severity = anomaly_data.get('severity', 'UNKNOWN')
    timestamp = anomaly_data.get('timestamp', int(datetime.now().timestamp()))
    cpu_value = anomaly_data.get('value', 0)
    z_score = anomaly_data.get('z_score', 0)
    hampel_score = anomaly_data.get('hampel_score', False)
    methods_triggered = anomaly_data.get('methods_triggered', [])
    
    # Format timestamp
    try:
        formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        formatted_time = 'Unknown'
    
    # Create subject line
    subject = f"🚨 {severity} Anomaly Alert - Device {device_id}"
    
    # Build comprehensive message
    message_parts = [
        f"ANOMALY DETECTION ALERT",
        f"========================",
        f"",
        f"🔴 SEVERITY: {severity}",
        f"📱 DEVICE ID: {device_id}",
        f"⏰ TIME: {formatted_time}",
        f"",
        f"📊 ANOMALY DETAILS:",
        f"   • CPU Usage: {cpu_value}%",
        f"   • Z-Score: {z_score:.2f}",
        f"   • Hampel Filter: {'Triggered' if hampel_score else 'Not Triggered'}",
        f"   • Methods Triggered: {', '.join(methods_triggered) if methods_triggered else 'None'}",
        f"   • Method Count: {anomaly_data.get('method_count', 0)}",
        f""
    ]
    
    # Add additional metrics if available
    if anomaly_data.get('ewma_score'):
        message_parts.append(f"   • EWMA Score: {anomaly_data.get('ewma_score', 0):.2f}")
    
    if anomaly_data.get('rate_of_change'):
        message_parts.append(f"   • Rate of Change: {anomaly_data.get('rate_of_change', 0):.2f}")
    
    if anomaly_data.get('cpu_mean'):
        message_parts.append(f"   • CPU Mean: {anomaly_data.get('cpu_mean', 0):.2f}%")
        message_parts.append(f"   • CPU Std Dev: {anomaly_data.get('cpu_std', 0):.2f}")
    
    message_parts.append(f"")
    
    # Add device information if available
    if device_info:
        message_parts.extend([
            f"🏷️ DEVICE INFORMATION:",
            f"   • Product Name: {device_info.get('productName', 'Unknown')}",
            f"   • Model: {device_info.get('modelNo', 'Unknown')}",
            f"   • Location: {device_info.get('location', anomaly_data.get('device_location', 'Unknown'))}",
            f"   • Device Type: {device_info.get('device_type', anomaly_data.get('device_type', 'Unknown'))}",
            f"   • Hostname: {device_info.get('hostname', anomaly_data.get('device_name', 'Unknown'))}",
            f""
        ])
    else:
        # Use metadata from anomaly data if device info not available
        message_parts.extend([
            f"🏷️ DEVICE INFORMATION:",
            f"   • Location: {anomaly_data.get('device_location', 'Unknown')}",
            f"   • Device Name: {anomaly_data.get('device_name', 'Unknown')}",
            f"   • Device Type: {anomaly_data.get('device_type', 'Unknown')}",
            f""
        ])
    
    # Add original data context
    original_data = anomaly_data.get('original_data', {})
    if original_data:
        message_parts.extend([
            f"📋 ORIGINAL DATA CONTEXT:",
            f"   • Hostname: {original_data.get('hostname', 'Unknown')}",
            f"   • Location: {original_data.get('location', 'Unknown')}",
            f"   • Raw CPU Usage: {original_data.get('cpu_usage', 'Unknown')}%",
            f""
        ])
    
    # Add batch information
    if anomaly_data.get('batchStartTime') and anomaly_data.get('batchEndTime'):
        try:
            batch_start = datetime.fromtimestamp(anomaly_data.get('batchStartTime')).strftime('%H:%M:%S')
            batch_end = datetime.fromtimestamp(anomaly_data.get('batchEndTime')).strftime('%H:%M:%S')
            message_parts.extend([
                f"⏱️ BATCH INFORMATION:",
                f"   • Batch Start: {batch_start}",
                f"   • Batch End: {batch_end}",
                f"   • Anomaly Count: {anomaly_data.get('anomalyCount', 1)}",
                f""
            ])
        except:
            pass
    
    # Add severity-specific recommendations
    if severity == 'CRITICAL':
        message_parts.extend([
            f"🚨 IMMEDIATE ACTION REQUIRED:",
            f"   • Multiple anomaly detection methods triggered",
            f"   • CPU usage significantly above normal thresholds",
            f"   • Recommend immediate investigation",
            f""
        ])
    elif severity == 'HIGH':
        message_parts.extend([
            f"⚠️ HIGH PRIORITY:",
            f"   • Significant anomaly detected",
            f"   • Monitor device closely",
            f"   • Consider preventive maintenance",
            f""
        ])
    elif severity == 'MEDIUM':
        message_parts.extend([
            f"📋 MEDIUM PRIORITY:",
            f"   • Anomaly detected within acceptable range",
            f"   • Monitor trends for patterns",
            f""
        ])
    
    # Add footer
    message_parts.extend([
        f"📊 This alert contains ALL data received by the EventBridge system.",
        f"🔗 For detailed analysis, check your monitoring dashboard.",
        f"",
        f"Generated by IoT Anomaly Detection System",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    ])
    
    return subject, '\n'.join(message_parts)

def lambda_handler(event, context):
    """
    AWS Lambda handler for processing EventBridge anomaly events and sending SNS notifications
    Contains ALL data received by EventBridge
    
    Args:
        event (dict): EventBridge event with complete anomaly data
        context (object): AWS Lambda context object
        
    Returns:
        dict: Response with status code and notification details
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
        
        # Extract complete event details
        detail = event.get('detail', {})
        device_id = detail.get('device_id')
        severity = detail.get('severity', 'UNKNOWN')
        
        if not device_id:
            logger.error("Missing device_id in event")
            return {
                'statusCode': 400,
                'body': json.dumps('Missing device_id in event')
            }
        
        # Check if notification should be sent based on severity threshold
        if not should_send_notification(severity, NOTIFICATION_THRESHOLD):
            logger.info(f"Skipping notification for {severity} severity (threshold: {NOTIFICATION_THRESHOLD})")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Notification skipped - below threshold',
                    'device_id': device_id,
                    'severity': severity,
                    'threshold': NOTIFICATION_THRESHOLD
                })
            }
        
        # Get device information for enriched notifications
        device_info = get_device_info(device_id)
        
        # Format notification message with ALL EventBridge data
        subject, message = format_notification_message(device_id, detail, device_info)
        
        # Send SNS notification
        try:
            response = sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject,
                Message=message
            )
            
            message_id = response.get('MessageId')
            logger.info(f"Successfully sent SNS notification: {message_id}")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Successfully sent anomaly notification',
                    'device_id': device_id,
                    'severity': severity,
                    'sns_message_id': message_id,
                    'notification_sent': True,
                    'data_included': 'all_eventbridge_data'
                })
            }
            
        except Exception as e:
            logger.error(f"Failed to send SNS notification: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps(f'Error sending SNS notification: {str(e)}')
            }
    
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing SNS notification: {str(e)}')
        }