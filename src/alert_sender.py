"""
Alert sending module for Email and Slack notifications.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
import requests

logger = logging.getLogger(__name__)


class AlertSender:
    """Sends alerts via Email and Slack."""
    
    def __init__(self, alert_config: Dict[str, Any]):
        """
        Initialize alert sender.
        
        Args:
            alert_config: Alert configuration dictionary
        """
        self.alert_config = alert_config
        self.email_config = alert_config.get('email', {})
        self.slack_config = alert_config.get('slack', {})
    
    def send_kpi_alert(self, kpi_result: Dict[str, Any]) -> bool:
        """
        Send alert for a KPI anomaly.
        
        Args:
            kpi_result: KPI result dictionary
            
        Returns:
            True if alert sent successfully
        """
        if not kpi_result.get('alert_enabled', False):
            logger.debug(f"Alerts disabled for KPI: {kpi_result.get('kpi_name')}")
            return False
        
        success = True
        
        # Send email alert
        if self.email_config.get('enabled', False):
            if not self._send_email_alert(kpi_result):
                success = False
        
        # Send Slack alert
        if self.slack_config.get('enabled', False):
            if not self._send_slack_alert(kpi_result):
                success = False
        
        return success
    
    def _send_email_alert(self, kpi_result: Dict[str, Any]) -> bool:
        """Send email alert."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['smtp_user']
            msg['To'] = ', '.join(self.email_config['recipients'])
            msg['Subject'] = f"🚨 KPI Alert: {kpi_result.get('kpi_name')}"
            
            body = self._format_email_body(kpi_result)
            msg.attach(MIMEText(body, 'html'))
            
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['smtp_user'], self.email_config['smtp_password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email alert sent for KPI: {kpi_result.get('kpi_name')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
            return False
    
    def _send_slack_alert(self, kpi_result: Dict[str, Any]) -> bool:
        """Send Slack alert."""
        try:
            webhook_url = self.slack_config['webhook_url']
            
            # Determine color based on priority
            priority = kpi_result.get('alert_priority', 'medium')
            color_map = {
                'high': 'danger',
                'medium': 'warning',
                'low': 'good'
            }
            color = color_map.get(priority, 'warning')
            
            details = kpi_result.get('anomaly_details', {})
            change_percent = details.get('change_percent', 0)
            
            # Determine emoji based on change direction
            if change_percent < 0:
                emoji = "📉"
                trend = "decreased"
            else:
                emoji = "📈"
                trend = "increased"
            
            payload = {
                "channel": self.slack_config.get('channel', '#kpi-alerts'),
                "username": "KPI Monitor",
                "icon_emoji": ":warning:",
                "text": f"{emoji} *KPI Alert: {kpi_result.get('kpi_name')}*",
                "attachments": [
                    {
                        "color": color,
                        "fields": [
                            {
                                "title": "Description",
                                "value": kpi_result.get('description', 'N/A'),
                                "short": False
                            },
                            {
                                "title": "Current Value",
                                "value": f"{kpi_result.get('current_value', 'N/A'):,.2f}" if isinstance(kpi_result.get('current_value'), (int, float)) else str(kpi_result.get('current_value', 'N/A')),
                                "short": True
                            },
                            {
                                "title": "Status",
                                "value": kpi_result.get('status', 'N/A').upper(),
                                "short": True
                            },
                            {
                                "title": "Change",
                                "value": f"{change_percent:.2f}% {trend}",
                                "short": True
                            },
                            {
                                "title": "Baseline",
                                "value": f"{details.get('baseline', 'N/A'):,.2f}" if isinstance(details.get('baseline'), (int, float)) else str(details.get('baseline', 'N/A')),
                                "short": True
                            }
                        ],
                        "footer": f"Priority: {priority.upper()}",
                        "ts": int(kpi_result.get('timestamp', '').replace(':', '').replace('-', '')[:10]) if kpi_result.get('timestamp') else None
                    }
                ]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Slack alert sent for KPI: {kpi_result.get('kpi_name')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {str(e)}")
            return False
    
    def _format_email_body(self, kpi_result: Dict[str, Any]) -> str:
        """Format email body as HTML."""
        details = kpi_result.get('anomaly_details', {})
        change_percent = details.get('change_percent', 0)
        priority = kpi_result.get('alert_priority', 'medium')
        
        # Color coding
        if change_percent < 0:
            change_color = "red"
            trend_icon = "📉"
        else:
            change_color = "orange"
            trend_icon = "📈"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #f44336; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .metric {{ background-color: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid #2196F3; }}
                .alert {{ background-color: #fff3cd; border-left-color: #ffc107; }}
                .value {{ font-size: 24px; font-weight: bold; color: #333; }}
                .change {{ color: {change_color}; font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🚨 KPI Alert: {kpi_result.get('kpi_name')}</h2>
                <p>Priority: {priority.upper()}</p>
            </div>
            <div class="content">
                <p><strong>Description:</strong> {kpi_result.get('description', 'N/A')}</p>
                <p><strong>Status:</strong> <span style="color: red; font-weight: bold;">{kpi_result.get('status', 'N/A').upper()}</span></p>
                
                <div class="metric alert">
                    <h3>Current Metrics</h3>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
                        <tr>
                            <td>Current Value</td>
                            <td class="value">{kpi_result.get('current_value', 'N/A'):,.2f if isinstance(kpi_result.get('current_value'), (int, float)) else kpi_result.get('current_value', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Baseline</td>
                            <td>{details.get('baseline', 'N/A'):,.2f if isinstance(details.get('baseline'), (int, float)) else details.get('baseline', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Change {trend_icon}</td>
                            <td class="change">{change_percent:.2f}%</td>
                        </tr>
                        <tr>
                            <td>Threshold</td>
                            <td>{kpi_result.get('threshold_type', 'N/A')} ({kpi_result.get('threshold_value', 'N/A')})</td>
                        </tr>
                    </table>
                </div>
                
                <hr>
                <p><em>Timestamp: {kpi_result.get('timestamp', 'N/A')}</em></p>
                <p><em>This is an automated alert from the KPI Monitoring System.</em></p>
            </div>
        </body>
        </html>
        """
        return html

