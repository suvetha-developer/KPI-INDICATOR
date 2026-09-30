"""
Flask web dashboard for real-time KPI monitoring.
Run with: python dashboard.py
"""
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
from typing import Dict, List, Any

# #region agent log
import time
DEBUG_LOG_PATH = Path(__file__).parent / '.cursor' / 'debug.log'
def debug_log(location, message, data=None, hypothesis_id=None):
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG_PATH, 'a', encoding='utf-8') as f:
            log_entry = {
                'id': f'log_{int(time.time() * 1000)}',
                'timestamp': int(time.time() * 1000),
                'location': location,
                'message': message,
                'data': data or {},
                'sessionId': 'debug-session',
                'runId': 'run1',
                'hypothesisId': hypothesis_id
            }
            f.write(json.dumps(log_entry) + '\n')
    except: pass
# #endregion

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database import DatabaseConnection
from src.kpi_calculator import KPICalculator
from src.synthetic_generator import generator as synthetic_generator
from src.data_quality import dq_engine
from src.anomaly_detector import anomaly_detector
from src.powerbi_exporter import powerbi_exporter
from src.predictive_engine import predictive_engine
from src.root_cause_analyzer import root_cause_analyzer
from src.incident_manager import incident_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kpi-monitor-secret-key'

# Global variables for KPI data
kpi_monitor = None
last_update = None


def initialize_monitor():
    """Initialize KPI monitor."""
    global kpi_monitor
    # #region agent log
    debug_log('dashboard.py:34', 'initialize_monitor ENTRY', {}, 'A')
    # #endregion
    try:
        config_path = Path("config/kpi_config.json")
        # #region agent log
        debug_log('dashboard.py:38', 'BEFORE config file read', {'config_path': str(config_path), 'exists': config_path.exists()}, 'E')
        # #endregion
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        # #region agent log
        debug_log('dashboard.py:41', 'AFTER config file read', {'has_database': 'database' in config}, 'E')
        # #endregion
        
        db_config = config.get('database', {})
        # #region agent log
        debug_log('dashboard.py:43', 'BEFORE db connection', {'db_type': db_config.get('type'), 'db_path': db_config.get('database')}, 'A')
        # #endregion
        db = DatabaseConnection(db_config)
        db.connect()
        # #region agent log
        debug_log('dashboard.py:44', 'AFTER db.connect()', {'connected': True}, 'A')
        # #endregion
        
        # #region agent log
        debug_log('dashboard.py:46', 'BEFORE KPICalculator init', {'config_path': str(config_path)}, 'C')
        # #endregion
        kpi_monitor = KPICalculator(db, str(config_path))
        kpi_monitor.db = db  # Store db reference
        # #region agent log
        debug_log('dashboard.py:47', 'AFTER KPICalculator init', {'kpi_monitor_created': kpi_monitor is not None}, 'C')
        # #endregion
        
        logger.info("KPI Monitor initialized")
        # #region agent log
        debug_log('dashboard.py:50', 'initialize_monitor EXIT SUCCESS', {'return': True}, 'A')
        # #endregion
        return True
    except Exception as e:
        # #region agent log
        debug_log('dashboard.py:52', 'initialize_monitor EXCEPTION', {'error': str(e), 'error_type': type(e).__name__}, 'A')
        # #endregion
        logger.error(f"Failed to initialize monitor: {str(e)}")
        return False


@app.route('/')
def index():
    """Main dashboard page."""
    # #region agent log
    debug_log('dashboard.py:57', 'index() ENTRY', {}, 'B')
    # #endregion
    try:
        # #region agent log
        template_path = Path(__file__).parent / 'templates' / 'dashboard.html'
        debug_log('dashboard.py:59', 'BEFORE render_template', {'template_exists': template_path.exists(), 'template_path': str(template_path)}, 'B')
        # #endregion
        result = render_template('dashboard.html')
        # #region agent log
        debug_log('dashboard.py:59', 'AFTER render_template', {'success': True, 'result_length': len(result) if result else 0}, 'B')
        # #endregion
        return result
    except Exception as e:
        # #region agent log
        debug_log('dashboard.py:59', 'render_template EXCEPTION', {'error': str(e), 'error_type': type(e).__name__}, 'B')
        # #endregion
        raise


@app.route('/api/kpis')
def get_kpis():
    """Get current KPI values."""
    global last_update
    # #region agent log
    debug_log('dashboard.py:63', 'get_kpis() ENTRY', {'kpi_monitor_exists': kpi_monitor is not None}, 'C')
    # #endregion
    try:
        if not kpi_monitor:
            # #region agent log
            debug_log('dashboard.py:69', 'kpi_monitor is None, calling initialize_monitor', {}, 'A')
            # #endregion
            if not initialize_monitor():
                return jsonify({'error': 'Failed to initialize monitor'}), 500
        
        # Calculate all KPIs
        # #region agent log
        debug_log('dashboard.py:73', 'BEFORE calculate_all_kpis', {'kpi_monitor_type': type(kpi_monitor).__name__}, 'C')
        # #endregion
        kpi_results = kpi_monitor.calculate_all_kpis()
        # #region agent log
        debug_log('dashboard.py:73', 'AFTER calculate_all_kpis', {'results_count': len(kpi_results) if kpi_results else 0, 'first_result_status': kpi_results[0].get('status') if kpi_results else None}, 'C')
        # #endregion
        last_update = datetime.now().isoformat()
        
        # Format results for frontend
        formatted_results = []
        # #region agent log
        debug_log('dashboard.py:77', 'BEFORE formatting results', {'kpi_results_count': len(kpi_results)}, 'C')
        # #endregion
        for result in kpi_results:
            details = result.get('anomaly_details', {})
            change_percent = details.get('change_percent', 0)
            
            formatted_results.append({
                'name': result.get('kpi_name', 'Unknown'),
                'description': result.get('description', ''),
                'value': result.get('current_value', 0),
                'status': result.get('status', 'normal'),
                'change_percent': round(change_percent, 2),
                'baseline': details.get('baseline', 0),
                'threshold_type': result.get('threshold_type', ''),
                'threshold_value': result.get('threshold_value', 0),
                'priority': result.get('alert_priority', 'medium'),
                'timestamp': result.get('timestamp', '')
            })
        # #region agent log
        debug_log('dashboard.py:95', 'AFTER formatting results', {'formatted_count': len(formatted_results)}, 'C')
        # #endregion
        
        response_data = {
            'kpis': formatted_results,
            'last_update': last_update,
            'total': len(formatted_results),
            'alerts': sum(1 for r in formatted_results if r['status'] == 'alert'),
            'normal': sum(1 for r in formatted_results if r['status'] == 'normal'),
            'errors': sum(1 for r in formatted_results if r['status'] == 'error')
        }
        # #region agent log
        debug_log('dashboard.py:102', 'get_kpis() EXIT SUCCESS', {'response_total': response_data['total']}, 'C')
        # #endregion
        return jsonify(response_data)
        
    except Exception as e:
        # #region agent log
        debug_log('dashboard.py:104', 'get_kpis() EXCEPTION', {'error': str(e), 'error_type': type(e).__name__}, 'C')
        # #endregion
        logger.error(f"Error getting KPIs: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/refresh')
def refresh_kpis():
    """Force refresh of KPIs."""
    global last_update
    
    try:
        if not kpi_monitor:
            if not initialize_monitor():
                return jsonify({'error': 'Failed to initialize monitor'}), 500
        
        # Recalculate KPIs
        kpi_results = kpi_monitor.calculate_all_kpis()
        last_update = datetime.now().isoformat()
        
        alerts = sum(1 for r in kpi_results if r.get('status') == 'alert')
        
        return jsonify({
            'success': True,
            'message': 'KPIs refreshed successfully',
            'alerts': alerts,
            'timestamp': last_update
        })
        
    except Exception as e:
        logger.error(f"Error refreshing KPIs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """Get system status."""
    return jsonify({
        'status': 'running',
        'last_update': last_update,
        'monitor_initialized': kpi_monitor is not None,
        'synthetic_stream': synthetic_generator.get_status()
    })


# -------------------------------------------------------------------------
# Real-Time Synthetic Dataset & Anomaly Injection Endpoints
# -------------------------------------------------------------------------

@app.route('/api/synthetic/status', methods=['GET'])
def get_synthetic_status():
    """Get real-time synthetic generator status."""
    return jsonify(synthetic_generator.get_status())


@app.route('/api/synthetic/stream/start', methods=['POST'])
def start_synthetic_stream():
    """Start real-time synthetic order streaming."""
    data = request.get_json(silent=True) or {}
    interval = float(data.get('interval', 5.0))
    mode = data.get('mode', 'NORMAL')
    synthetic_generator.start_realtime_stream(interval_seconds=interval, mode=mode)
    return jsonify({
        'success': True,
        'message': f'Real-time synthetic stream started in {mode} mode ({interval}s interval)',
        'status': synthetic_generator.get_status()
    })


@app.route('/api/synthetic/stream/stop', methods=['POST'])
def stop_synthetic_stream():
    """Stop real-time synthetic order streaming."""
    synthetic_generator.stop_realtime_stream()
    return jsonify({
        'success': True,
        'message': 'Real-time synthetic stream paused',
        'status': synthetic_generator.get_status()
    })


@app.route('/api/synthetic/inject', methods=['POST'])
def inject_synthetic_batch():
    """Inject a targeted batch of synthetic orders or anomaly scenario."""
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'NORMAL').upper()
    count = int(data.get('count', 25))

    if mode == 'CHURN_SPIKE':
        result = synthetic_generator.inject_churn_anomaly_cohort(churn_count=count)
    elif mode == 'DATA_QUALITY_ANOMALY':
        result = synthetic_generator.inject_data_quality_anomaly()
    else:
        result = synthetic_generator.inject_batch(count=count, mode=mode)

    return jsonify(result)


# -------------------------------------------------------------------------
# Automated Data Quality (DQ) Audit Endpoints
# -------------------------------------------------------------------------

@app.route('/api/data-quality/audit', methods=['GET'])
def run_data_quality_audit():
    """Run automated SQL & Python data quality checks."""
    try:
        report = dq_engine.run_all_checks()
        return jsonify(report)
    except Exception as e:
        logger.error(f"Data quality audit error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/data-quality/clean', methods=['POST'])
def clean_data_quality():
    """Remediate injected data quality test records."""
    try:
        res = dq_engine.clean_known_anomalies()
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------------------
# Statistical Trend & Anomaly Detection Endpoints
# -------------------------------------------------------------------------

@app.route('/api/anomalies/trends', methods=['GET'])
def get_operational_trends():
    """Analyze time series data using Z-score and moving averages."""
    try:
        trends = anomaly_detector.analyze_operational_trends()
        return jsonify(trends)
    except Exception as e:
        logger.error(f"Anomaly trend analysis error: {e}")
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------------------
# Power BI Integration & Dataset Export Endpoints
# -------------------------------------------------------------------------

@app.route('/api/powerbi/export', methods=['POST'])
def export_powerbi_dataset():
    """Export operational datasets to CSV and refresh SQL views for Power BI."""
    try:
        res = powerbi_exporter.export_all_datasets()
        return jsonify(res)
    except Exception as e:
        logger.error(f"Power BI export error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/powerbi/dax', methods=['GET'])
def get_powerbi_dax():
    """Retrieve pre-built Power BI DAX measures."""
    dax_path = Path(__file__).parent / 'powerbi' / 'DAX_MEASURES.dax'
    if dax_path.exists():
        with open(dax_path, 'r', encoding='utf-8') as f:
            dax_content = f.read()
        return jsonify({'success': True, 'dax': dax_content})
    return jsonify({'error': 'DAX file not found'}), 404


# -------------------------------------------------------------------------
# Predictive Forecasting & What-If Simulation Endpoints
# -------------------------------------------------------------------------

@app.route('/api/forecast', methods=['GET'])
def get_predictive_forecast():
    """Get 7-day statistical forecast with early warning indicators."""
    horizon = int(request.args.get('days', 7))
    try:
        res = predictive_engine.generate_forecast(horizon_days=horizon)
        return jsonify(res)
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulate/what-if', methods=['POST'])
def simulate_what_if():
    """Simulate business impact of pricing, churn, and shipping changes."""
    data = request.get_json(silent=True) or {}
    price_change = float(data.get('price_change_pct', 0.0))
    churn_change = float(data.get('churn_change_pct', 0.0))
    delivery_delay = float(data.get('delivery_delay_days', 0.0))
    try:
        res = predictive_engine.simulate_what_if_scenario(
            price_change_pct=price_change,
            churn_change_pct=churn_change,
            delivery_delay_days=delivery_delay
        )
        return jsonify(res)
    except Exception as e:
        logger.error(f"What-if simulation error: {e}")
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------------------
# Automated Root-Cause Analysis (RCA) Endpoints
# -------------------------------------------------------------------------

@app.route('/api/root-cause/diagnose', methods=['GET'])
def diagnose_root_cause():
    """Execute automated drill-down across Geography, Category, Payment, Logistics."""
    kpi = request.args.get('kpi', 'daily_revenue')
    try:
        res = root_cause_analyzer.diagnose_operational_anomaly(kpi_name=kpi)
        return jsonify(res)
    except Exception as e:
        logger.error(f"RCA error: {e}")
        return jsonify({'error': str(e)}), 500


# -------------------------------------------------------------------------
# Incident Lifecycle & Multi-Channel Webhook Dispatcher
# -------------------------------------------------------------------------

@app.route('/api/incidents', methods=['GET'])
def list_incidents():
    """Get recent operational incidents."""
    try:
        incidents = incident_manager.list_incidents()
        return jsonify({'incidents': incidents})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/incidents/<incident_id>/ack', methods=['POST'])
def acknowledge_incident(incident_id):
    """Acknowledge incident by on-call user."""
    data = request.get_json(silent=True) or {}
    ack_by = data.get('user', 'On-Call Engineer')
    res = incident_manager.acknowledge_incident(incident_id, ack_by=ack_by)
    return jsonify(res)


@app.route('/api/incidents/<incident_id>/resolve', methods=['POST'])
def resolve_incident(incident_id):
    """Mark incident resolved with operator notes."""
    data = request.get_json(silent=True) or {}
    notes = data.get('notes', 'Resolved via operational dashboard')
    res = incident_manager.resolve_incident(incident_id, notes=notes)
    return jsonify(res)


@app.route('/api/alerts/webhook/test', methods=['POST'])
def test_webhook():
    """Send test alert card to Slack or Teams."""
    data = request.get_json(silent=True) or {}
    url = data.get('webhook_url', '')
    p_type = data.get('type', 'slack')
    res = incident_manager.dispatch_webhook_notification(url, payload_type=p_type)
    return jsonify(res)



if __name__ == '__main__':
    # #region agent log
    debug_log('dashboard.py:147', 'MAIN ENTRY', {'cwd': str(Path.cwd())}, 'D')
    # #endregion
    # Initialize monitor on startup
    init_result = initialize_monitor()
    # #region agent log
    debug_log('dashboard.py:149', 'AFTER initialize_monitor in main', {'init_result': init_result}, 'D')
    # #endregion
    if init_result:
        logger.info("Starting KPI Dashboard on http://localhost:5000")
        # #region agent log
        debug_log('dashboard.py:151', 'BEFORE app.run', {'host': '0.0.0.0', 'port': 5000}, 'D')
        # #endregion
        try:
            app.run(debug=True, host='0.0.0.0', port=5000)
        except Exception as e:
            # #region agent log
            debug_log('dashboard.py:151', 'app.run EXCEPTION', {'error': str(e), 'error_type': type(e).__name__}, 'D')
            # #endregion
            raise
    else:
        # #region agent log
        debug_log('dashboard.py:153', 'initialize_monitor FAILED, exiting', {}, 'A')
        # #endregion
        logger.error("Failed to start dashboard - check configuration")
        sys.exit(1)

