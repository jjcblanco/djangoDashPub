#!/usr/bin/env python
"""
Run comprehensive security audit and generate PDF report
"""
import os
import sys
import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from security_audit import SecurityAudit, main as run_audit
from pdf_generator import generate_security_audit_pdf


def main():
    """Run security audit and generate PDF report"""
    print("=" * 80)
    print("CRYPTO TRADING DASHBOARD - SECURITY AUDIT")
    print("=" * 80)
    
    # Run security audit
    print("\nRunning security audit...")
    audit = run_audit()
    
    # Get report text and findings
    report_text = audit.get_report_text()
    findings = audit.get_findings()
    
    # Generate PDF
    print("\nGenerating PDF report...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"security_audit_report_{timestamp}.pdf"
    
    try:
        pdf_path = generate_security_audit_pdf(
            audit_report=report_text,
            findings=findings,
            output_filename=pdf_filename
        )
        print(f"[OK] PDF report generated: {pdf_path}")
    except Exception as e:
        print(f"[ERROR] Error generating PDF: {e}")
        print("Generating text report only...")
        
        # Save text report as fallback
        text_filename = f"security_audit_report_{timestamp}.txt"
        with open(text_filename, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"✓ Text report saved: {text_filename}")
        pdf_path = None
    
    # Summary
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)
    
    # Count findings by severity
    severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for finding in findings:
        severity = finding.get('severity', '').upper()
        if severity in severity_counts:
            severity_counts[severity] += 1
    
    print(f"\nFindings Summary:")
    print(f"  Critical: {severity_counts['CRITICAL']}")
    print(f"  High: {severity_counts['HIGH']}")
    print(f"  Medium: {severity_counts['MEDIUM']}")
    print(f"  Low: {severity_counts['LOW']}")
    print(f"  Total: {len(findings)}")
    
    # Overall risk level
    if severity_counts['CRITICAL'] > 0:
        risk_level = "[CRITICAL]"
    elif severity_counts['HIGH'] > 0:
        risk_level = "[HIGH]"
    elif severity_counts['MEDIUM'] > 0:
        risk_level = "[MEDIUM]"
    else:
        risk_level = "[LOW]"
    
    print(f"\nOverall Risk Level: {risk_level}")
    
    if pdf_path:
        print(f"\nReport available at: {os.path.abspath(pdf_path)}")
    
    # Recommendations
    if findings:
        print("\nTop Recommendations:")
        high_priority = [f for f in findings if f.get('severity') in ['CRITICAL', 'HIGH']]
        for i, finding in enumerate(high_priority[:3], 1):
            rec = finding.get('recommendation')
            if rec:
                print(f"  {i}. {rec}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()