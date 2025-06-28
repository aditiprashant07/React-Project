import json
import boto3
import time
from datetime import datetime
from statistics import mean, stdev, median
from collections import deque
import logging
import os
import base64
import pickle

# Configure logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Initialize AWS clients
try:
    REGION = os.environ.get('REGION', 'ap-northeast-1')
    eventbridge = boto3.client('events', region_name=REGION)
    s3 = boto3.client('s3', region_name=REGION)
    logger.info("AWS clients initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AWS clients: {str(e)}")
    raise

# Configuration from environment variables
STREAM_NAME = os.environ.get('STREAM_NAME', 'iotstuff_iot_data_stream')
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'iotstuff')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', f'{PROJECT_NAME}_anomaly_bus')
HOSTNAME = os.environ.get('HOSTNAME', 'laptop01')
LOCATION = os.environ.get('LOCATION', 'local')
S3_BUCKET = os.environ.get('S3_BUCKET', 'my-lambda-state-bucket')
S3_KEY = os.environ.get('S3_KEY', 'anomaly_detection_state.pkl')
BASELINE_S3_KEY = os.environ.get('BASELINE_S3_KEY', 'baseline_values.pkl')

# Constants
WINDOW_SIZE = 100
ALPHA = 0.1
LAMBDA_ = 0.98
DEFAULT_THRESHOLDS = {
    'z_score': 2.5, 'ewma_score': 2.0, 'rate_of_change': 20.0,
    'mad': 3.5, 'hampel': 3.0
}
HAMPEL_K = 7

def check_baseline_exists():
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=BASELINE_S3_KEY)
        return True
    except s3.exceptions.ClientError:
        return False

def save_baseline_values(cpu_values):
    try:
        if len(cpu_values) < 2: return False
        cpu_array = list(cpu_values)
        mean_val, std_val = mean(cpu_array), stdev(cpu_array)
        baseline = {
            'mean': mean_val, 'std': std_val, 'median': median(cpu_array),
            'z_score_threshold': max(2.0, min(3.0, mean_val / std_val if std_val > 0 else 2.5)),
            'ewma_score_threshold': max(1.5, min(2.5, 2 * std_val / mean_val if mean_val > 0 else 2.0)),
            'rate_of_change_threshold': max(15.0, min(25.0, 3 * std_val)),
            'mad_threshold': max(3.0, min(4.0, 3.5 + std_val / 10)),
            'hampel_threshold': max(2.5, min(3.5, 3.0 + std_val / 20)),
        }
        s3.put_object(Bucket=S3_BUCKET, Key=BASELINE_S3_KEY, Body=pickle.dumps(baseline))
        logger.info("Baseline values saved to S3.")
        return True
    except Exception as e:
        logger.error(f"Failed to save baseline: {e}")
        return False

def load_baseline():
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=BASELINE_S3_KEY)
        return pickle.loads(response['Body'].read())
    except Exception: return None

def load_state():
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        state = pickle.loads(response['Body'].read())
        return (deque(state['cpu_history'], maxlen=WINDOW_SIZE),
                state.get('ewma_cpu'), state.get('ewmstd_cpu', 1), state.get('last_cpu'))
    except s3.exceptions.NoSuchKey:
        return deque(maxlen=WINDOW_SIZE), None, 1, None
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        return deque(maxlen=WINDOW_SIZE), None, 1, None

def save_state(cpu_history, ewma_cpu, ewmstd_cpu, last_cpu):
    try:
        state = {'cpu_history': list(cpu_history), 'ewma_cpu': ewma_cpu,
                 'ewmstd_cpu': ewmstd_cpu, 'last_cpu': last_cpu}
        s3.put_object(Bucket=S3_BUCKET, Key=S3_KEY, Body=pickle.dumps(state))
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def calculate_adaptive_thresholds(cpu_history):
    baseline = load_baseline()
    if baseline:
        return {k.replace('_threshold', ''): v for k, v in baseline.items() if k.endswith('_threshold')}
    if len(cpu_history) < WINDOW_SIZE // 2: return DEFAULT_THRESHOLDS
    data = list(cpu_history)
    mean_val, std = mean(data), stdev(data) if len(data) > 1 else 1.0
    return {
        'z_score': max(2.0, min(3.0, mean_val / std if std > 0 else 2.5)),
        'ewma_score': max(1.5, min(2.5, 2 * std / mean_val if mean_val > 0 else 2.0)),
        'rate_of_change': max(15.0, min(25.0, 3 * std)),
        'mad': max(3.0, min(4.0, 3.5 + std / 10)),
        'hampel': max(2.5, min(3.5, 3.0 + std / 20))
    }

def modified_z_score(data, threshold):
    med = median(data); mad = median([abs(x - med) for x in data])
    if mad == 0: return False
    return (0.6745 * (data[-1] - med)) / mad > threshold

def hampel_filter(data, k, threshold):
    if len(data) < 2 * k + 1: return False
    window = data[-(2*k+1):-1]
    med = median(window); mad = median([abs(x - med) for x in window])
    if mad == 0: return False
    return abs(data[-1] - med) / mad > threshold

def determine_severity(count, scores, thresholds):
    if (count >= 4 or scores['z_score'] > thresholds['z_score'] * 2): return 'CRITICAL'
    if (count >= 3 or scores['z_score'] > thresholds['z_score'] * 1.5): return 'HIGH'
    return 'MEDIUM'

def detect_anomaly(cpu, cpu_history, ewma_cpu, ewmstd_cpu, last_cpu):
    cpu_history.append(cpu)
    if len(cpu_history) < WINDOW_SIZE // 2:
        return None, ewma_cpu, ewmstd_cpu, cpu

    history_list = list(cpu_history)
    thresholds = calculate_adaptive_thresholds(history_list)
    mean_val, std_val = mean(history_list), stdev(history_list) if len(history_list) > 1 else 1.0
    
    if ewma_cpu is None: ewma_cpu = mean_val
    ewma_cpu = ALPHA * cpu + (1 - ALPHA) * ewma_cpu
    ewma_dev = abs(cpu - ewma_cpu)
    ewmstd_cpu = ((LAMBDA_ * (ewmstd_cpu**2) + (1 - LAMBDA_) * (ewma_dev**2)) ** 0.5) if ewmstd_cpu is not None else 1.0
    
    scores = {
        'z_score': abs((cpu - mean_val) / std_val),
        'ewma_score': ewma_dev / (ewmstd_cpu or 1.0),
        'rate_of_change': abs(cpu - last_cpu) if last_cpu is not None else 0
    }
    
    triggered_methods = [method for method, score in scores.items() if score > thresholds[method]]
    if modified_z_score(history_list, thresholds['mad']): triggered_methods.append('mad')
    if hampel_filter(history_list, HAMPEL_K, thresholds['hampel']): triggered_methods.append('hampel')

    if len(triggered_methods) >= 2:
        severity = determine_severity(len(triggered_methods), scores, thresholds)
        anomaly_report = {
            'value': cpu, 'severity': severity, 'methods_triggered': triggered_methods,
            'method_count': len(triggered_methods), 'z_score': scores['z_score'],
            'ewma_score': scores['ewma_score'], 'rate_of_change': scores['rate_of_change'],
            'hampel_score': 'hampel' in triggered_methods,
            'cpu_mean': mean_val, 'cpu_std': std_val,
            # *** NEW: Include the entire data window in the report ***
            'cpu_window': history_list
        }
        logger.info(f"🚨 Anomaly Detected! Severity: {severity}, Methods: {triggered_methods}")
        return anomaly_report, ewma_cpu, ewmstd_cpu, cpu

    return None, ewma_cpu, ewmstd_cpu, cpu

def send_to_eventbridge(anomaly_report, timestamp, device_id):
    try:
        detail = {k: v for k, v in anomaly_report.items()}
        # Add identifying info
        detail['device_id'] = device_id
        detail['timestamp'] = timestamp
        detail['anomaly_type'] = 'cpu_usage'
        detail['device_location'] = LOCATION
        detail['device_name'] = HOSTNAME
        
        event_entry = {
            'Source': f'{PROJECT_NAME}.anomaly-detection', 'DetailType': 'AnomalyDetected',
            'Detail': json.dumps(detail, default=str), 'EventBusName': EVENT_BUS_NAME
        }
        eventbridge.put_events(Entries=[event_entry])
        logger.info("✅ Successfully sent AnomalyDetected event to EventBridge.")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send event to EventBridge: {e}")
        return False

def lambda_handler(event, context):
    cpu_history, ewma_cpu, ewmstd_cpu, last_cpu = load_state()
    records_processed = 0
    anomalies_detected = 0