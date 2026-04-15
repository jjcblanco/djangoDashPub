#!/usr/bin/env python3
"""
WebSocket Configuration Script for Django Channels with Apache

This script generates configuration files for deploying Django Channels
with Daphne ASGI server behind Apache proxy.

Usage:
    python configure_websockets.py --apache --systemd --output-dir=/path/to/output

Requirements:
    - Django Channels already installed and configured
    - Apache with mod_proxy_wstunnel enabled
    - Daphne installed in virtual environment
"""

import os
import sys
import argparse
import textwrap

def generate_apache_config(project_path, domain, venv_path, daphne_port=8001):
    """Generate Apache configuration for WebSocket proxy"""
    
    config = f"""
# Apache WebSocket Proxy Configuration for Django Channels
# Add this to your Apache site configuration or .htaccess

<VirtualHost *:80>
    ServerName {domain}
    
    # Static files
    Alias /static/ "{project_path}/static/"
    <Directory "{project_path}/static/">
        Require all granted
    </Directory>
    
    # Media files
    Alias /media/ "{project_path}/media/"
    <Directory "{project_path}/media/">
        Require all granted
    </Directory>
    
    # WebSocket proxy
    RewriteEngine On
    RewriteCond %{{HTTP:Upgrade}} websocket [NC]
    RewriteCond %{{HTTP:Connection}} upgrade [NC]
    RewriteRule ^/?(.*) "ws://127.0.0.1:{daphne_port}/$1" [P,L]
    
    ProxyPreserveHost On
    ProxyPass /ws/ ws://127.0.0.1:{daphne_port}/ws/
    ProxyPassReverse /ws/ ws://127.0.0.1:{daphne_port}/ws/
    
    # HTTP proxy for Daphne
    ProxyPass / http://127.0.0.1:{daphne_port}/
    ProxyPassReverse / http://127.0.0.1:{daphne_port}/
    
    # Alternative: Keep WSGI for HTTP, Daphne only for WebSockets
    # WSGIDaemonProcess criptodash python-path="{project_path}:{venv_path}/lib/python3.12/site-packages"
    # WSGIProcessGroup criptodash
    # WSGIScriptAlias / "{project_path}/criptodash/wsgi.py"
    
    <Directory "{project_path}/criptodash">
        <Files "wsgi.py">
            Require all granted
        </Files>
    </Directory>
    
    ErrorLog ${{APACHE_LOG_DIR}}/criptodash_error.log
    CustomLog ${{APACHE_LOG_DIR}}/criptodash_access.log combined
</VirtualHost>

# If using HTTPS
<VirtualHost *:443>
    ServerName {domain}
    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/ssl-cert-snakeoil.pem
    SSLCertificateKeyFile /etc/ssl/private/ssl-cert-snakeoil.key
    
    # Same WebSocket proxy configuration as above
    RewriteEngine On
    RewriteCond %{{HTTP:Upgrade}} websocket [NC]
    RewriteCond %{{HTTP:Connection}} upgrade [NC]
    RewriteRule ^/?(.*) "wss://127.0.0.1:{daphne_port}/$1" [P,L]
    
    ProxyPreserveHost On
    ProxyPass /ws/ wss://127.0.0.1:{daphne_port}/ws/
    ProxyPassReverse /ws/ wss://127.0.0.1:{daphne_port}/ws/
    
    ProxyPass / https://127.0.0.1:{daphne_port}/
    ProxyPassReverse / https://127.0.0.1:{daphne_port}/
</VirtualHost>
"""
    
    # Also generate minimal config for existing Apache setup
    minimal_config = f"""
# Minimal WebSocket proxy addition to existing Apache config
# Add these lines to your existing VirtualHost configuration

RewriteEngine On
RewriteCond %{{HTTP:Upgrade}} websocket [NC]
RewriteCond %{{HTTP:Connection}} upgrade [NC]
RewriteRule ^/?(.*) "ws://127.0.0.1:{daphne_port}/$1" [P,L]

ProxyPreserveHost On
ProxyPass /ws/ ws://127.0.0.1:{daphne_port}/ws/
ProxyPassReverse /ws/ ws://127.0.0.1:{daphne_port}/ws/
"""
    
    return {
        'full_config': config,
        'minimal_config': minimal_config
    }

def generate_systemd_service(project_path, venv_path, user, daphne_port=8001):
    """Generate systemd service file for Daphne"""
    
    service_content = f"""[Unit]
Description=Daphne ASGI server for CriptoDash
After=network.target
Requires=celery.service
After=celery.service

[Service]
Type=simple
User={user}
Group={user}
WorkingDirectory={project_path}
Environment="PATH={venv_path}/bin"
Environment="DJANGO_SETTINGS_MODULE=criptodash.settings"
ExecStart={venv_path}/bin/daphne -b 0.0.0.0 -p {daphne_port} criptodash.asgi:application
Restart=on-failure
RestartSec=10
KillSignal=SIGINT
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    return service_content

def generate_supervisor_config(project_path, venv_path, user, daphne_port=8001):
    """Generate Supervisor configuration for Daphne"""
    
    config = f"""[program:daphne]
command={venv_path}/bin/daphne -b 0.0.0.0 -p {daphne_port} criptodash.asgi:application
directory={project_path}
user={user}
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile={project_path}/logs/daphne.log
stderr_logfile={project_path}/logs/daphne_error.log
environment=DJANGO_SETTINGS_MODULE="criptodash.settings",PATH="{venv_path}/bin"
"""
    
    return config

def generate_setup_script():
    """Generate bash setup script"""
    
    script = """#!/bin/bash
# WebSocket Setup Script for Django Channels
# Run as root or with sudo

set -e

echo "🔧 Setting up WebSocket support for CriptoDash"

# Install Daphne
echo "📦 Installing Daphne..."
pip install daphne channels channels-redis

# Enable Apache modules
echo "🌐 Enabling Apache modules..."
a2enmod proxy
a2enmod proxy_http
a2enmod proxy_wstunnel
a2enmod rewrite
a2enmod headers

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p /var/log/daphne
chown www-data:www-data /var/log/daphne

# Create systemd service
echo "⚙️ Creating systemd service..."
cat > /etc/systemd/system/daphne.service << 'EOF'
[Unit]
Description=Daphne ASGI server for CriptoDash
After=network.target
Requires=celery.service
After=celery.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/criptodash
Environment="PATH=/var/www/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=criptodash.settings"
ExecStart=/var/www/venv/bin/daphne -b 0.0.0.0 -p 8001 criptodash.asgi:application
Restart=on-failure
RestartSec=10
KillSignal=SIGINT
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "🎯 Configuration generated!"
echo ""
echo "Next steps:"
echo "1. Add WebSocket proxy configuration to Apache"
echo "2. Reload Apache: sudo systemctl reload apache2"
echo "3. Enable and start Daphne: sudo systemctl enable --now daphne"
echo "4. Check status: sudo systemctl status daphne"
echo ""
echo "For troubleshooting, check logs:"
echo "  sudo journalctl -u daphne -f"
echo "  sudo tail -f /var/log/apache2/error.log"
"""
    
    return script

def main():
    parser = argparse.ArgumentParser(description='Generate WebSocket configuration files')
    parser.add_argument('--apache', action='store_true', help='Generate Apache configuration')
    parser.add_argument('--systemd', action='store_true', help='Generate systemd service file')
    parser.add_argument('--supervisor', action='store_true', help='Generate Supervisor configuration')
    parser.add_argument('--setup-script', action='store_true', help='Generate setup bash script')
    parser.add_argument('--output-dir', default='.', help='Output directory for generated files')
    parser.add_argument('--project-path', default='/var/www/criptodash', help='Project directory path')
    parser.add_argument('--venv-path', default='/var/www/venv', help='Virtual environment path')
    parser.add_argument('--domain', default='whale-tracking.example.com', help='Domain name')
    parser.add_argument('--user', default='www-data', help='System user to run Daphne')
    parser.add_argument('--port', type=int, default=8001, help='Daphne port')
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    generated_files = []
    
    if args.apache:
        configs = generate_apache_config(
            args.project_path, args.domain, args.venv_path, args.port
        )
        
        # Write full config
        full_config_path = os.path.join(args.output_dir, 'apache_websocket.conf')
        with open(full_config_path, 'w') as f:
            f.write(configs['full_config'])
        generated_files.append(full_config_path)
        print(f"✅ Generated Apache config: {full_config_path}")
        
        # Write minimal config
        minimal_config_path = os.path.join(args.output_dir, 'apache_websocket_minimal.conf')
        with open(minimal_config_path, 'w') as f:
            f.write(configs['minimal_config'])
        generated_files.append(minimal_config_path)
        print(f"✅ Generated minimal Apache config: {minimal_config_path}")
    
    if args.systemd:
        service_content = generate_systemd_service(
            args.project_path, args.venv_path, args.user, args.port
        )
        
        service_path = os.path.join(args.output_dir, 'daphne.service')
        with open(service_path, 'w') as f:
            f.write(service_content)
        generated_files.append(service_path)
        print(f"✅ Generated systemd service: {service_path}")
    
    if args.supervisor:
        supervisor_config = generate_supervisor_config(
            args.project_path, args.venv_path, args.user, args.port
        )
        
        supervisor_path = os.path.join(args.output_dir, 'daphne_supervisor.conf')
        with open(supervisor_path, 'w') as f:
            f.write(supervisor_config)
        generated_files.append(supervisor_path)
        print(f"✅ Generated Supervisor config: {supervisor_path}")
    
    if args.setup_script:
        script_content = generate_setup_script()
        
        script_path = os.path.join(args.output_dir, 'setup_websockets.sh')
        with open(script_path, 'w') as f:
            f.write(script_content)
        # Make executable
        os.chmod(script_path, 0o755)
        generated_files.append(script_path)
        print(f"✅ Generated setup script: {script_path}")
    
    if not generated_files:
        print("⚠️ No configurations generated. Use --apache, --systemd, --supervisor, or --setup-script")
        parser.print_help()
    else:
        print(f"\n🎉 Generated {len(generated_files)} configuration file(s)")
        print("\n📋 NEXT STEPS:")
        print("1. Copy configuration files to appropriate locations:")
        print("   - Apache config: /etc/apache2/sites-available/ or include in existing config")
        print("   - systemd service: /etc/systemd/system/daphne.service")
        print("2. Enable required Apache modules:")
        print("   sudo a2enmod proxy proxy_http proxy_wstunnel rewrite headers")
        print("3. Install Daphne in virtual environment:")
        print("   pip install daphne channels channels-redis")
        print("4. Reload Apache and start Daphne:")
        print("   sudo systemctl reload apache2")
        print("   sudo systemctl enable --now daphne")
        print("5. Verify WebSocket connection at: ws://your-domain/ws/whale-metrics/")

if __name__ == '__main__':
    main()