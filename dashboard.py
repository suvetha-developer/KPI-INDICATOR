"""
Flask web dashboard for real-time KPI monitoring.
Run with: python dashboard.py
"""
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify
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
        'monitor_initialized': kpi_monitor is not None
    })


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

