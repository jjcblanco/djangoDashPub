# Deploy — CriptoDash en el VPS

Units systemd de producción. Instalar con:

```bash
sudo cp deploy/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now criptodash-daphne celery-worker celery-beat criptobots
```

## Flujo de deploy seguro

```bash
cd /var/www/clients/client2/web5/web/criptodash/
source /var/www/javierblanco.com.ar/web/venv/bin/activate

# 0. Pausar bots antes de migrar
python manage.py shell -c "from dashboard.models import LiveBot; LiveBot.objects.filter(status='RUNNING').update(status='PAUSED')"

# 1. Backup de BD (imprescindible antes de migrate)
sudo mysqldump --no-defaults -u root -h 127.0.0.1 trading_db > /root/backup_criptodash_$(date +%F).sql

# 2. Desplegar código
git pull origin main
pip install -r requirements.txt

# 3. Verificar drift ANTES de migrar
python manage.py showmigrations dashboard
python manage.py migrate --plan
python manage.py makemigrations --check --dry-run   # debe decir "No changes detected"

# 4. Migrar + check
python manage.py migrate
python manage.py check --deploy

# 5. Reiniciar servicios en este orden
sudo systemctl restart criptodash-daphne celery-worker celery-beat criptobots
sudo systemctl reload apache2

# 6. Verificar
curl -I -H "Host: javierblanco.com.ar" http://127.0.0.1:8001/   # esperado: 200/302
```

## Notas

- **Permisos de logs**: si Daphne falla con `ValueError: Unable to configure handler 'error_file'`:
  `sudo chown -R web5:client2 /var/www/clients/client2/web5/web/criptodash/logs/ && sudo chmod -R 775 .../logs/`
- **Redis**: el OOM (`OutOfMemoryError` en login) se arregla con `redis-cli FLUSHDB` y `maxmemory-policy allkeys-lru` en /etc/redis/redis.conf.
  Bases de datos separadas: 0=broker Celery, 1=caché Django, 2=channels.
- **Historia de git reescrita**: si `git pull` da "refusing to merge unrelated histories", hacer backup de rama
  (`git branch backup/pre-rewrite-<fecha>`) y `git reset --hard origin/main`. NO pushear la rama backup (contiene secretos).

## Migraciones — plan de squash (pendiente, solo en ventana de mantenimiento)

- Existe un "diamante" de migraciones: dos archivos `0002_*` (`0002_add_pairref.py` y `0002_remove_indicators_constraint.py`).
  Funciona en producción (Django los distingue por nombre completo), pero `migrate dashboard 0002` es ambiguo y
  `squashmigrations` se confunde.
- **No renombrar los archivos**: rompería producción (Django los vería como no aplicados).
- Plan futuro: consolidar 0001→0040 con `squashmigrations` en una ventana de mantenimiento con la BD detenida,
  verificando antes con `showmigrations dashboard` que no haya migraciones fakeadas a mano.
