"""
PDF Generator for Security Audit Reports
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os


class SecurityAuditPDF:
    """Generate PDF reports for security audits"""
    
    def __init__(self, filename=None):
        self.filename = filename or f"security_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        self.doc = SimpleDocTemplate(
            self.filename,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        self.styles = getSampleStyleSheet()
        self.elements = []
        
        # Custom styles
        self._create_custom_styles()
        
    def _create_custom_styles(self):
        """Create custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='AuditTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.darkblue,
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Heading1 style
        self.styles.add(ParagraphStyle(
            name='AuditHeading1',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.darkblue,
            spaceBefore=20,
            spaceAfter=10,
            underline=True
        ))
        
        # Heading2 style
        self.styles.add(ParagraphStyle(
            name='AuditHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.darkgreen,
            spaceBefore=15,
            spaceAfter=8
        ))
        
        # Normal style
        self.styles.add(ParagraphStyle(
            name='AuditNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))
        
        # Finding style - Critical
        self.styles.add(ParagraphStyle(
            name='FindingCritical',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.red,
            backColor=colors.lightgrey,
            spaceAfter=4,
            leftIndent=20
        ))
        
        # Finding style - High
        self.styles.add(ParagraphStyle(
            name='FindingHigh',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.orangered,
            spaceAfter=4,
            leftIndent=20
        ))
        
        # Finding style - Medium
        self.styles.add(ParagraphStyle(
            name='FindingMedium',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.orange,
            spaceAfter=4,
            leftIndent=20
        ))
        
        # Finding style - Low
        self.styles.add(ParagraphStyle(
            name='FindingLow',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.darkgreen,
            spaceAfter=4,
            leftIndent=20
        ))
        
        # Info style
        self.styles.add(ParagraphStyle(
            name='AuditInfo',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            spaceAfter=3,
            leftIndent=10
        ))
        
        # Code style
        self.styles.add(ParagraphStyle(
            name='AuditCode',
            parent=self.styles['Code'],
            fontSize=8,
            fontName='Courier',
            textColor=colors.darkslategray,
            backColor=colors.whitesmoke,
            spaceAfter=6,
            leftIndent=20
        ))
        
    def add_title(self, title="Security Audit Report", subtitle=None):
        """Add title page"""
        # Main title
        self.elements.append(Paragraph(title, self.styles['AuditTitle']))
        self.elements.append(Spacer(1, 0.5*inch))
        
        # Subtitle
        if subtitle:
            self.elements.append(Paragraph(subtitle, self.styles['AuditHeading2']))
            self.elements.append(Spacer(1, 0.3*inch))
        
        # Date
        date_str = datetime.now().strftime("%B %d, %Y at %H:%M:%S")
        self.elements.append(Paragraph(f"Generated on: {date_str}", self.styles['AuditNormal']))
        self.elements.append(Spacer(1, 0.5*inch))
        
        # System info
        self.elements.append(Paragraph("Crypto Trading Dashboard Security Audit", self.styles['AuditHeading2']))
        self.elements.append(Spacer(1, 0.8*inch))
        
    def add_executive_summary(self, summary_data):
        """Add executive summary section"""
        self.elements.append(Paragraph("Executive Summary", self.styles['AuditHeading1']))
        self.elements.append(Spacer(1, 0.2*inch))
        
        # Risk level box
        risk_level = summary_data.get('risk_level', 'UNKNOWN')
        risk_color = {
            'CRITICAL': colors.red,
            'HIGH': colors.orangered,
            'MEDIUM': colors.orange,
            'LOW': colors.darkgreen,
            'UNKNOWN': colors.grey
        }.get(risk_level.upper(), colors.grey)
        
        risk_table = Table([
            ["Overall Risk Level:", risk_level]
        ], colWidths=[2*inch, 3*inch])
        
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, 0), risk_color),
            ('TEXTCOLOR', (1, 0), (1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        self.elements.append(risk_table)
        self.elements.append(Spacer(1, 0.3*inch))
        
        # Findings summary table
        findings_data = [
            ["Critical Findings", str(summary_data.get('critical_count', 0))],
            ["High Findings", str(summary_data.get('high_count', 0))],
            ["Medium Findings", str(summary_data.get('medium_count', 0))],
            ["Low Findings", str(summary_data.get('low_count', 0))],
            ["Total Findings", str(summary_data.get('total_findings', 0))],
            ["Errors During Audit", str(summary_data.get('error_count', 0))]
        ]
        
        findings_table = Table(findings_data, colWidths=[3*inch, 1*inch])
        findings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.red),
            ('BACKGROUND', (0, 1), (0, 1), colors.orangered),
            ('BACKGROUND', (0, 2), (0, 2), colors.orange),
            ('BACKGROUND', (0, 3), (0, 3), colors.lightgreen),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        self.elements.append(findings_table)
        self.elements.append(Spacer(1, 0.3*inch))
        
        # Key recommendations
        recommendations = summary_data.get('recommendations', [])
        if recommendations:
            self.elements.append(Paragraph("Key Recommendations:", self.styles['AuditHeading2']))
            for i, rec in enumerate(recommendations[:5], 1):
                self.elements.append(Paragraph(f"{i}. {rec}", self.styles['AuditNormal']))
        
        self.elements.append(PageBreak())
        
    def add_findings_table(self, findings):
        """Add detailed findings table"""
        self.elements.append(Paragraph("Detailed Findings", self.styles['AuditHeading1']))
        self.elements.append(Spacer(1, 0.2*inch))
        
        if not findings:
            self.elements.append(Paragraph("No findings to report.", self.styles['AuditNormal']))
            self.elements.append(Spacer(1, 0.2*inch))
            return
        
        # Prepare table data
        table_data = [["Severity", "Category", "Description", "Recommendation"]]
        
        for finding in findings:
            severity = finding.get('severity', 'UNKNOWN')
            category = finding.get('category', '')
            description = finding.get('description', '')[:100] + "..." if len(finding.get('description', '')) > 100 else finding.get('description', '')
            recommendation = finding.get('recommendation', 'N/A')[:80] + "..." if len(finding.get('recommendation', '')) > 80 else finding.get('recommendation', 'N/A')
            
            table_data.append([severity, category, description, recommendation])
        
        # Create table
        table = Table(table_data, colWidths=[0.8*inch, 1.2*inch, 3*inch, 2.5*inch])
        
        # Define style
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Row colors based on severity
            ('TEXTCOLOR', (0, 1), (0, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
        ])
        
        # Color severity cells
        for i, row in enumerate(table_data[1:], 1):
            severity = row[0].upper()
            severity_color = {
                'CRITICAL': colors.red,
                'HIGH': colors.orangered,
                'MEDIUM': colors.orange,
                'LOW': colors.lightgreen
            }.get(severity, colors.white)
            
            style.add('BACKGROUND', (0, i), (0, i), severity_color)
            if severity in ['CRITICAL', 'HIGH']:
                style.add('TEXTCOLOR', (0, i), (0, i), colors.white)
        
        table.setStyle(style)
        self.elements.append(table)
        self.elements.append(PageBreak())
        
    def add_section(self, title, content_items):
        """Add a section with title and content items"""
        self.elements.append(Paragraph(title, self.styles['AuditHeading1']))
        self.elements.append(Spacer(1, 0.1*inch))
        
        for item in content_items:
            if isinstance(item, dict):
                # Handle finding item
                severity = item.get('severity', 'INFO').upper()
                description = item.get('description', '')
                recommendation = item.get('recommendation')
                
                style_name = {
                    'CRITICAL': 'FindingCritical',
                    'HIGH': 'FindingHigh',
                    'MEDIUM': 'FindingMedium',
                    'LOW': 'FindingLow'
                }.get(severity, 'AuditInfo')
                
                self.elements.append(Paragraph(f"<b>{severity}:</b> {description}", self.styles[style_name]))
                
                if recommendation:
                    self.elements.append(Paragraph(f"<i>Recommendation:</i> {recommendation}", self.styles['AuditInfo']))
                    
            elif isinstance(item, str):
                # Handle simple text item
                if item.startswith('INFO:'):
                    self.elements.append(Paragraph(item, self.styles['AuditInfo']))
                elif item.startswith('ERROR:'):
                    self.elements.append(Paragraph(item, self.styles['FindingCritical']))
                elif ':' in item and len(item) < 100:
                    # Likely a key-value pair
                    self.elements.append(Paragraph(item, self.styles['AuditNormal']))
                else:
                    self.elements.append(Paragraph(item, self.styles['AuditNormal']))
            elif isinstance(item, list):
                # Handle list of items
                for subitem in item:
                    self.elements.append(Paragraph(f"• {subitem}", self.styles['AuditNormal']))
        
        self.elements.append(Spacer(1, 0.2*inch))
        
    def add_raw_text(self, text):
        """Add raw text content"""
        lines = text.split('\n')
        for line in lines:
            if line.strip():
                if line.startswith('==='):
                    # Section header
                    self.elements.append(Paragraph(line.strip('=').strip(), self.styles['AuditHeading2']))
                elif line.startswith('[') and ']' in line:
                    # Finding line
                    severity_end = line.find(']')
                    severity = line[1:severity_end]
                    description = line[severity_end+2:]
                    
                    style_name = {
                        'CRITICAL': 'FindingCritical',
                        'HIGH': 'FindingHigh',
                        'MEDIUM': 'FindingMedium',
                        'LOW': 'FindingLow'
                    }.get(severity.upper(), 'AuditNormal')
                    
                    self.elements.append(Paragraph(description, self.styles[style_name]))
                elif line.startswith('INFO:'):
                    self.elements.append(Paragraph(line, self.styles['AuditInfo']))
                elif line.startswith('ERROR:'):
                    self.elements.append(Paragraph(line, self.styles['FindingCritical']))
                else:
                    self.elements.append(Paragraph(line, self.styles['AuditNormal']))
        
    def generate(self):
        """Generate the PDF document"""
        self.doc.build(self.elements)
        return self.filename


def generate_security_audit_pdf(audit_report, findings, output_filename=None):
    """
    Generate a PDF from security audit results
    
    Args:
        audit_report: Text report from security audit
        findings: List of finding dictionaries
        output_filename: Optional output filename
    
    Returns:
        Path to generated PDF
    """
    pdf = SecurityAuditPDF(output_filename)
    
    # Add title page
    pdf.add_title(
        title="Security Audit Report",
        subtitle="Crypto Trading Dashboard System"
    )
    
    # Calculate summary data
    severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    recommendations = []
    
    for finding in findings:
        severity = finding.get('severity', '').upper()
        if severity in severity_counts:
            severity_counts[severity] += 1
        
        rec = finding.get('recommendation')
        if rec and rec not in recommendations:
            recommendations.append(rec)
    
    total_findings = sum(severity_counts.values())
    
    # Determine overall risk level
    if severity_counts['CRITICAL'] > 0:
        risk_level = "CRITICAL"
    elif severity_counts['HIGH'] > 0:
        risk_level = "HIGH"
    elif severity_counts['MEDIUM'] > 0:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    # Add executive summary
    pdf.add_executive_summary({
        'risk_level': risk_level,
        'critical_count': severity_counts['CRITICAL'],
        'high_count': severity_counts['HIGH'],
        'medium_count': severity_counts['MEDIUM'],
        'low_count': severity_counts['LOW'],
        'total_findings': total_findings,
        'error_count': 0,  # Would need to track errors separately
        'recommendations': recommendations[:3]  # Top 3 recommendations
    })
    
    # Add detailed findings table
    pdf.add_findings_table(findings)
    
    # Add raw audit report
    pdf.add_section("Full Audit Report", [])
    pdf.add_raw_text(audit_report)
    
    # Generate PDF
    filename = pdf.generate()
    return filename


if __name__ == "__main__":
    # Example usage
    sample_findings = [
        {
            'severity': 'HIGH',
            'category': 'Configuration',
            'description': 'DEBUG mode is enabled in production environment',
            'recommendation': 'Set DEBUG=False in production'
        },
        {
            'severity': 'MEDIUM',
            'category': 'Database',
            'description': 'Using SQLite database (not recommended for production)',
            'recommendation': 'Consider using PostgreSQL or MySQL for production'
        }
    ]
    
    sample_report = """=== ENVIRONMENT CHECKS ===
INFO: Audit started at 2025-04-13 10:30:00
[CRITICAL] Configuration: Weak SECRET_KEY detected
   Recommendation: Generate a strong random SECRET_KEY
INFO: Database connection successful"""
    
    pdf_path = generate_security_audit_pdf(sample_report, sample_findings)
    print(f"PDF generated: {pdf_path}")