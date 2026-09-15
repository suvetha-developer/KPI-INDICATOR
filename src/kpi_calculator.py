"""
KPI calculation and anomaly detection module.
Calculates KPIs from database and detects anomalies using various methods.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import numpy as np

from src.database import DatabaseConnection

logger = logging.getLogger(__name__)


class KPICalculator:
    """Calculates KPIs and detects anomalies."""
    
    def __init__(self, db: DatabaseConnection, config_path: str):
        """
        Initialize KPI calculator.
        
        Args:
            db: Database connection instance
            config_path: Path to KPI configuration file
        """
        self.db = db
        self.config_path = Path(config_path)
        self.kpi_configs = self._load_kpi_configs()
        
    def _load_kpi_configs(self) -> List[Dict[str, Any]]:
        """Load KPI configurations from JSON file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return []
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('kpis', [])
    
    def calculate_all_kpis(self) -> List[Dict[str, Any]]:
        """
        Calculate all configured KPIs.
        
        Returns:
            List of KPI results with status
        """
        results = []
        
        if not self.kpi_configs:
            logger.warning("No KPI configurations found")
            return results
        
        logger.info(f"Calculating {len(self.kpi_configs)} KPIs...")
        
        for kpi_config in self.kpi_configs:
            try:
                result = self.calculate_kpi(kpi_config)
                results.append(result)
            except Exception as e:
                logger.error(f"Error calculating KPI {kpi_config.get('name')}: {str(e)}", exc_info=True)
                results.append({
                    'kpi_name': kpi_config.get('name', 'Unknown'),
                    'description': kpi_config.get('description', ''),
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        return results
    
    def calculate_kpi(self, kpi_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate a single KPI and check for anomalies.
        
        Args:
            kpi_config: KPI configuration dictionary
            
        Returns:
            KPI result dictionary with status
        """
        kpi_name = kpi_config.get('name')
        logger.info(f"Calculating KPI: {kpi_name}")
        
        # Execute SQL query to get current value
        current_query = kpi_config.get('sql_query')
        if not current_query:
            return {
                'kpi_name': kpi_name,
                'description': kpi_config.get('description', ''),
                'status': 'error',
                'error': 'No SQL query defined',
                'timestamp': datetime.now().isoformat()
            }
        
        try:
            current_results = self.db.execute_query(current_query)
        except Exception as e:
            logger.error(f"Query execution failed for {kpi_name}: {str(e)}")
            return {
                'kpi_name': kpi_name,
                'description': kpi_config.get('description', ''),
                'status': 'error',
                'error': f'Query execution failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
        
        if not current_results:
            return {
                'kpi_name': kpi_name,
                'description': kpi_config.get('description', ''),
                'status': 'error',
                'error': 'No data returned from query',
                'timestamp': datetime.now().isoformat()
            }
        
        current_value = current_results[0].get('value')
        if current_value is None:
            return {
                'kpi_name': kpi_name,
                'description': kpi_config.get('description', ''),
                'status': 'error',
                'error': 'Null value returned',
                'timestamp': datetime.now().isoformat()
            }
        
        # Convert to float
        try:
            current_value = float(current_value)
        except (ValueError, TypeError):
            return {
                'kpi_name': kpi_name,
                'description': kpi_config.get('description', ''),
                'status': 'error',
                'error': f'Invalid value type: {type(current_value)}',
                'timestamp': datetime.now().isoformat()
            }
        
        # Get historical data for comparison
        comparison_period = kpi_config.get('comparison_period', 'previous_week')
        historical_values = self._get_historical_values(kpi_config, comparison_period)
        
        # Detect anomaly
        status, anomaly_details = self._detect_anomaly(
            current_value,
            historical_values,
            kpi_config
        )
        
        result = {
            'kpi_name': kpi_name,
            'description': kpi_config.get('description', ''),
            'current_value': current_value,
            'historical_values': historical_values[-7:] if len(historical_values) > 7 else historical_values,  # Last 7 for reporting
            'status': status,
            'threshold_type': kpi_config.get('threshold_type'),
            'threshold_value': kpi_config.get('threshold_value'),
            'anomaly_details': anomaly_details,
            'alert_enabled': kpi_config.get('alert_enabled', False),
            'alert_priority': kpi_config.get('alert_priority', 'medium'),
            'timestamp': datetime.now().isoformat()
        }
        
        return result
    
    def _get_historical_values(self, kpi_config: Dict[str, Any], period: str) -> List[float]:
        """
        Get historical KPI values for comparison.
        
        Args:
            kpi_config: KPI configuration
            period: Comparison period (previous_week, previous_month, etc.)
            
        Returns:
            List of historical values
        """
        base_query = kpi_config.get('sql_query')
        if not base_query:
            return []
        
        # Modify query to get historical data
        # Replace date filter to get last 7-30 days depending on period
        days_back = 30 if period == 'previous_month' else 7
        
        # Create historical query by modifying the date filter
        historical_query = base_query
        
        # For SQLite, replace DATE('now', '-1 day') with a range
        if "DATE('now', '-1 day')" in historical_query:
            historical_query = historical_query.replace(
                "DATE('now', '-1 day')",
                f"DATE('now', '-{days_back} days')"
            )
            # Add date range condition
            if "WHERE" in historical_query.upper():
                historical_query += f" AND DATE(o.order_purchase_timestamp) >= DATE('now', '-{days_back} days')"
                
        # Handle DATE('now') pattern (NEW FIX)
        elif "DATE('now')" in historical_query and "DATE('now', '-" not in historical_query:
             # Override query for known KPIs to ensure correct history fetching
             if kpi_config.get('name') == 'daily_revenue':
                historical_query = f"""
                    SELECT COALESCE(SUM(op.payment_value), 0) as value 
                    FROM olist_order_payments_dataset op 
                    JOIN olist_orders_dataset o ON op.order_id = o.order_id 
                    WHERE DATE(o.order_purchase_timestamp) >= DATE('now', '-{days_back} days') 
                    AND DATE(o.order_purchase_timestamp) < DATE('now')
                    GROUP BY DATE(o.order_purchase_timestamp)
                """
             elif kpi_config.get('name') == 'daily_order_volume':
                 historical_query = f"""
                    SELECT COUNT(DISTINCT o.order_id) as value 
                    FROM olist_orders_dataset o 
                    WHERE DATE(o.order_purchase_timestamp) >= DATE('now', '-{days_back} days')
                    AND DATE(o.order_purchase_timestamp) < DATE('now')
                    GROUP BY DATE(o.order_purchase_timestamp)
                """
             elif kpi_config.get('name') == 'conversion_rate':
                historical_query = f"""
                    SELECT COALESCE(COUNT(CASE WHEN o.order_status = 'delivered' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 0) as value 
                    FROM olist_orders_dataset o 
                    WHERE DATE(o.order_purchase_timestamp) >= DATE('now', '-{days_back} days')
                    AND DATE(o.order_purchase_timestamp) < DATE('now')
                    GROUP BY DATE(o.order_purchase_timestamp)
                """
             elif kpi_config.get('name') == 'customer_churn_rate':
                 # Use previous month window for churn
                 historical_query = f"""
                    SELECT COALESCE(COUNT(DISTINCT c.customer_id) * 100.0 / NULLIF((SELECT COUNT(DISTINCT customer_id) FROM olist_orders_dataset WHERE DATE(order_purchase_timestamp) >= DATE('now', '-90 days') AND DATE(order_purchase_timestamp) < DATE('now', '-60 days')), 0), 0) as value 
                    FROM olist_customers_dataset c WHERE c.customer_id IN (SELECT DISTINCT customer_id FROM olist_orders_dataset WHERE DATE(order_purchase_timestamp) >= DATE('now', '-90 days') AND DATE(order_purchase_timestamp) < DATE('now', '-60 days')) AND c.customer_id NOT IN (SELECT DISTINCT customer_id FROM olist_orders_dataset WHERE DATE(order_purchase_timestamp) >= DATE('now', '-60 days'))
                 """
        
        # Also handle other date patterns
        historical_query = historical_query.replace(
            "DATE('now', '-7 days')",
            f"DATE('now', '-{days_back} days')"
        )
        historical_query = historical_query.replace(
            "DATE('now', '-30 days')",
            f"DATE('now', '-{days_back} days')"
        )
        historical_query = historical_query.replace(
            "DATE('now', '-60 days')",
            f"DATE('now', '-{days_back + 30} days')"
        )
        
        # Modify to get daily values instead of single aggregate
        # This is a simplified approach - for production, you'd want more sophisticated query modification
        # For now, we'll get the aggregate and use it as baseline
        
        try:
            # Try to get daily breakdown if possible
            # This is a simplified version - in production, you'd parse and modify the query more intelligently
            results = self.db.execute_query(historical_query)
            
            # If we get multiple rows, return all values
            if len(results) > 1:
                return [float(r.get('value', 0)) for r in results if r.get('value') is not None]
            # If single value, create a list with that value repeated (simplified baseline)
            elif len(results) == 1:
                value = float(results[0].get('value', 0))
                # Return a list with the value repeated a few times to simulate historical data
                # In production, you'd want actual daily historical values
                return [value] * 5  # Simplified: use same value as baseline
            else:
                return []
                
        except Exception as e:
            logger.warning(f"Could not fetch historical data for {kpi_config.get('name')}: {str(e)}")
            return []
    
    def _detect_anomaly(
        self,
        current_value: float,
        historical_values: List[float],
        kpi_config: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Detect if current KPI value is anomalous.
        
        Args:
            current_value: Current KPI value
            historical_values: Historical values for comparison
            kpi_config: KPI configuration
            
        Returns:
            Tuple of (status, anomaly_details)
        """
        if not historical_values or len(historical_values) == 0:
            return 'normal', {'message': 'No historical data available'}
        
        threshold_type = kpi_config.get('threshold_type', 'percentage_drop')
        threshold_value = kpi_config.get('threshold_value', 10)
        
        # Calculate baseline (mean of historical values)
        baseline = np.mean(historical_values) if historical_values else current_value
        std_dev = np.std(historical_values) if len(historical_values) > 1 else 0
        
        if baseline == 0:
            # If baseline is 0 and current is not, it's a spike
            if current_value > 0:
                return 'normal', {
                    'current_value': current_value,
                    'baseline': baseline,
                    'change_percent': 100.0,
                    'message': 'Baseline was zero, new value detected'
                }
            return 'normal', {'message': 'Both baseline and current are zero'}
        
        # Calculate change percentage
        change_percent = ((current_value - baseline) / baseline) * 100
        
        anomaly_details = {
            'current_value': current_value,
            'baseline': baseline,
            'change_percent': change_percent,
            'historical_mean': baseline,
            'historical_std': std_dev,
            'historical_count': len(historical_values)
        }
        
        # Check thresholds based on type
        if threshold_type == 'percentage_drop':
            if change_percent < -threshold_value:
                anomaly_details['threshold_breached'] = True
                anomaly_details['breach_amount'] = abs(change_percent) - threshold_value
                return 'alert', anomaly_details
                
        elif threshold_type == 'percentage_spike':
            if change_percent > threshold_value:
                anomaly_details['threshold_breached'] = True
                anomaly_details['breach_amount'] = change_percent - threshold_value
                return 'alert', anomaly_details
                
        elif threshold_type == 'absolute_drop':
            if (baseline - current_value) > threshold_value:
                anomaly_details['threshold_breached'] = True
                anomaly_details['breach_amount'] = (baseline - current_value) - threshold_value
                return 'alert', anomaly_details
                
        elif threshold_type == 'absolute_spike':
            if (current_value - baseline) > threshold_value:
                anomaly_details['threshold_breached'] = True
                anomaly_details['breach_amount'] = (current_value - baseline) - threshold_value
                return 'alert', anomaly_details
                
        elif threshold_type == 'statistical':
            # Z-score based detection
            if len(historical_values) > 1 and std_dev > 0:
                z_score = (current_value - baseline) / std_dev
                anomaly_details['z_score'] = z_score
                if abs(z_score) > threshold_value:  # threshold_value as z-score threshold
                    anomaly_details['threshold_breached'] = True
                    anomaly_details['breach_amount'] = abs(z_score) - threshold_value
                    return 'alert', anomaly_details
        
        # No anomaly detected
        anomaly_details['threshold_breached'] = False
        return 'normal', anomaly_details

