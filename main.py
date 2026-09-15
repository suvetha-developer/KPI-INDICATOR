"""
Main automation script for KPI monitoring and alerting.
Can be run manually or scheduled via Windows Task Scheduler / cron.
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database import DatabaseConnection
from src.kpi_calculator import KPICalculator
from src.alert_sender import AlertSender
from src.excel_reporter import ExcelReporter

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f"kpi_monitor_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class KPIMonitor:
    """Main KPI monitoring system."""
    
    def __init__(self, config_path: str = "config/kpi_config.json"):
        """
        Initialize KPI monitor.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.db = None
        self.kpi_calculator = None
        self.alert_sender = None
        self.excel_reporter = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def initialize(self):
        """Initialize all components."""
        logger.info("Initializing KPI Monitoring System...")
        
        # Initialize database connection
        db_config = self.config.get('database', {})
        self.db = DatabaseConnection(db_config)
        
        # Initialize KPI calculator
        self.kpi_calculator = KPICalculator(self.db, str(self.config_path))
        
        # Initialize alert sender
        alert_config = self.config.get('alerts', {})
        self.alert_sender = AlertSender(alert_config)
        
        # Initialize Excel reporter
        report_config = self.config.get('reporting', {})
        excel_path = report_config.get('excel_output_path', 'reports/kpi_report.xlsx')
        self.excel_reporter = ExcelReporter(excel_path)
        
        logger.info("Initialization complete")
    
    def run(self) -> Dict[str, Any]:
        """
        Run KPI monitoring process.
        
        Returns:
            Dictionary with execution results
        """
        logger.info("=" * 60)
        logger.info("Starting KPI Monitoring Run")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        
        try:
            # Calculate all KPIs
            logger.info("Calculating KPIs...")
            kpi_results = self.kpi_calculator.calculate_all_kpis()
            
            # Log results
            for result in kpi_results:
                status = result.get('status', 'unknown')
                kpi_name = result.get('kpi_name', 'Unknown')
                logger.info(f"KPI: {kpi_name} - Status: {status}")
            
            # Send alerts for KPIs in alert status
            logger.info("Checking for alerts...")
            alerts_sent = 0
            for kpi_result in kpi_results:
                if kpi_result.get('status') == 'alert':
                    logger.warning(f"Alert detected for KPI: {kpi_result.get('kpi_name')}")
                    if self.alert_sender.send_kpi_alert(kpi_result):
                        alerts_sent += 1
            
            # Generate Excel report
            logger.info("Generating Excel report...")
            report_config = self.config.get('reporting', {})
            include_charts = report_config.get('include_charts', True)
            excel_path = self.excel_reporter.create_report(kpi_results, include_charts)
            logger.info(f"Excel report saved to: {excel_path}")
            
            # Summary
            total_kpis = len(kpi_results)
            alert_kpis = sum(1 for r in kpi_results if r.get('status') == 'alert')
            normal_kpis = sum(1 for r in kpi_results if r.get('status') == 'normal')
            error_kpis = sum(1 for r in kpi_results if r.get('status') == 'error')
            
            summary = {
                'timestamp': datetime.now().isoformat(),
                'total_kpis': total_kpis,
                'alert_kpis': alert_kpis,
                'normal_kpis': normal_kpis,
                'error_kpis': error_kpis,
                'alerts_sent': alerts_sent,
                'excel_report': excel_path,
                'kpi_results': kpi_results
            }
            
            logger.info("=" * 60)
            logger.info("KPI Monitoring Run Complete")
            logger.info(f"Total KPIs: {total_kpis}")
            logger.info(f"Alerts: {alert_kpis}")
            logger.info(f"Normal: {normal_kpis}")
            logger.info(f"Errors: {error_kpis}")
            logger.info(f"Alerts Sent: {alerts_sent}")
            logger.info("=" * 60)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error during KPI monitoring run: {str(e)}", exc_info=True)
            raise
    
    def cleanup(self):
        """Clean up resources."""
        if self.db:
            self.db.close()
        logger.info("Cleanup complete")


def main():
    """Main entry point."""
    try:
        # Initialize monitor
        monitor = KPIMonitor()
        monitor.initialize()
        
        # Run monitoring
        results = monitor.run()
        
        # Cleanup
        monitor.cleanup()
        
        # Exit with appropriate code
        if results.get('error_kpis', 0) > 0:
            sys.exit(1)
        elif results.get('alert_kpis', 0) > 0:
            sys.exit(2)  # Alerts detected but no errors
        else:
            sys.exit(0)  # All normal
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

