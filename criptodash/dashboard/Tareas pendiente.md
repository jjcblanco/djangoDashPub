Resumen del estado
Superficie	Estado
Puerto 8443 (panel ISPConfig, PHP)	🔴 Expuesto → cerrar con ufw ahora
Puertos 8080 (página default estática) / 8081 (403)	🟡 Cerrables también
Puerto 80/443 (sitio)	🟢 Con mitigación upload_progress=Off + bloqueo multipart
PHP 8.2.21	⚠️ Sigue vulnerable hasta que Kali publique 8.4.27+


El plan de cierre

# 1. Ver a dónde redirige (confirma que es ISPConfig)
curl -skI --max-time 5 https://127.0.0.1:8443/ | grep -i location

# 2. Cerrar al mundo todos los puertos de administración
# (deja abiertos solo: SSH 22, web 80, web 443)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8080/tcp
sudo ufw deny 8081/tcp
sudo ufw deny 8443/tcp
sudo ufw enable
sudo ufw status
Si necesitás acceder al panel desde tu casa (IP fija o dinámica de tu proveedor), en vez de cerrar 8443 del todo:


# Tu IP pública actual: curl -s ifconfig.me
sudo ufw allow from TU_IP to any port 8443

