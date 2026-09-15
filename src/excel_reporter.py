"""
Excel report generation module.
Generates Excel reports with KPI data, charts, and color-coded status.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference, BarChart
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


class ExcelReporter:
    """Generates Excel reports with KPI data and charts."""
    
    def __init__(self, output_path: str):
        """
        Initialize Excel reporter.
        
        Args:
            output_path: Path to output Excel file
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def create_report(self, kpi_results: List[Dict[str, Any]], include_charts: bool = True) -> str:
        """
        Create Excel report from KPI results.
        
        Args:
            kpi_results: List of KPI result dictionaries
            include_charts: Whether to include charts
            
        Returns:
            Path to created Excel file
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "KPI Summary"
        
        # Add title
        ws['A1'] = "KPI Monitoring Report"
        ws['A1'].font = Font(size=16, bold=True)
        ws['A2'] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ws['A2'].font = Font(size=10, italic=True)
        ws.merge_cells('A1:F1')
        ws.merge_cells('A2:F2')
        
        # Header row (starting at row 4)
        headers = ['KPI Name', 'Description', 'Current Value', 'Status', 'Change %', 'Baseline', 'Timestamp']
        header_row = 4
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.value = header
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
        
        # Add data rows
        for idx, result in enumerate(kpi_results, start=header_row + 1):
            details = result.get('anomaly_details', {})
            change_percent = details.get('change_percent', 0)
            
            row_data = [
                result.get('kpi_name', 'N/A'),
                result.get('description', 'N/A'),
                result.get('current_value', 'N/A'),
                result.get('status', 'N/A').upper(),
                f"{change_percent:.2f}%" if change_percent is not None else 'N/A',
                f"{details.get('baseline', 'N/A'):,.2f}" if isinstance(details.get('baseline'), (int, float)) else str(details.get('baseline', 'N/A')),
                result.get('timestamp', 'N/A')[:19] if result.get('timestamp') else 'N/A'  # Format timestamp
            ]
            
            for col_idx, value in enumerate(row_data, start=1):
                cell = ws.cell(row=idx, column=col_idx)
                cell.value = value
                cell.alignment = Alignment(horizontal="left", vertical="center")
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
            
            # Color code status column (column 4)
            status_cell = ws.cell(row=idx, column=4)
            status = result.get('status', 'normal').lower()
            if status == 'alert':
                status_cell.fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                status_cell.font = Font(bold=True, color="FFFFFF")
            elif status == 'normal':
                status_cell.fill = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
                status_cell.font = Font(bold=True, color="000000")
            elif status == 'error':
                status_cell.fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
                status_cell.font = Font(bold=True, color="000000")
            
            # Color code change percentage (column 5)
            change_cell = ws.cell(row=idx, column=5)
            if change_percent is not None:
                if change_percent < -10:
                    change_cell.fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
                elif change_percent < 0:
                    change_cell.fill = PatternFill(start_color="FFD93D", end_color="FFD93D", fill_type="solid")
                elif change_percent > 10:
                    change_cell.fill = PatternFill(start_color="6BCF7F", end_color="6BCF7F", fill_type="solid")
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if cell.value:
                        cell_length = len(str(cell.value))
                        if cell_length > max_length:
                            max_length = cell_length
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Add summary sheet
        self._add_summary_sheet(wb, kpi_results)
        
        # Add charts if requested and data available
        if include_charts:
            self._add_charts_sheet(wb, kpi_results)
        
        # Save workbook
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.output_path.parent / f"kpi_report_{timestamp}.xlsx"
        wb.save(report_path)
        logger.info(f"Excel report created: {report_path}")
        
        return str(report_path)
    
    def _add_summary_sheet(self, wb: Workbook, kpi_results: List[Dict[str, Any]]):
        """Add summary statistics sheet."""
        ws = wb.create_sheet("Summary")
        
        # Title
        ws['A1'] = "KPI Summary Statistics"
        ws['A1'].font = Font(size=14, bold=True)
        
        # Calculate statistics
        total = len(kpi_results)
        alerts = sum(1 for r in kpi_results if r.get('status') == 'alert')
        normal = sum(1 for r in kpi_results if r.get('status') == 'normal')
        errors = sum(1 for r in kpi_results if r.get('status') == 'error')
        
        # Summary data
        summary_data = [
            ['Metric', 'Value'],
            ['Total KPIs', total],
            ['Alerts', alerts],
            ['Normal', normal],
            ['Errors', errors],
            ['Alert Rate', f"{(alerts/total*100):.2f}%" if total > 0 else "0%"],
            ['', ''],
            ['Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        for row_idx, row_data in enumerate(summary_data, start=3):
            for col_idx, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.value = value
                if row_idx == 3:  # Header row
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
                    cell.border = Border(
                        left=Side(style='thin'),
                        right=Side(style='thin'),
                        top=Side(style='thin'),
                        bottom=Side(style='thin')
                    )
        
        # Auto-adjust column widths
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 15
    
    def _add_charts_sheet(self, wb: Workbook, kpi_results: List[Dict[str, Any]]):
        """Add charts sheet with visualizations."""
        ws = wb.create_sheet("Charts")
        
        # Title
        ws['A1'] = "KPI Visualizations"
        ws['A1'].font = Font(size=14, bold=True)
        
        # Create a simple bar chart for KPI values
        # Filter out errors and get top KPIs by value
        valid_kpis = [r for r in kpi_results if r.get('status') != 'error' and isinstance(r.get('current_value'), (int, float))]
        
        if not valid_kpis:
            ws['A3'] = "No valid KPI data available for charts"
            return
        
        # Sort by value (descending) and take top 10
        valid_kpis.sort(key=lambda x: abs(x.get('current_value', 0)), reverse=True)
        top_kpis = valid_kpis[:10]
        
        # Prepare data for chart
        chart_row_start = 3
        ws.cell(row=chart_row_start, column=1, value="KPI Name")
        ws.cell(row=chart_row_start, column=2, value="Current Value")
        
        for idx, kpi in enumerate(top_kpis, start=chart_row_start + 1):
            ws.cell(row=idx, column=1, value=kpi.get('kpi_name', 'Unknown'))
            ws.cell(row=idx, column=2, value=kpi.get('current_value', 0))
        
        # Create bar chart
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = "Top KPIs by Current Value"
        chart.y_axis.title = "Value"
        chart.x_axis.title = "KPI"
        
        data = Reference(ws, min_col=2, min_row=chart_row_start, max_row=chart_row_start + len(top_kpis))
        cats = Reference(ws, min_col=1, min_row=chart_row_start + 1, max_row=chart_row_start + len(top_kpis))
        chart.add_data(data, titles_from_data=False)
        chart.set_categories(cats)
        
        # Position chart
        ws.add_chart(chart, "D3")
        
        # Auto-adjust column widths
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 15

