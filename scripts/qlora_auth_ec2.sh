#!/bin/bash
# Este script solo prepara OAuth: nunca imprime tokens ni credenciales.
set -euo pipefail
if [ ! -x /opt/citas/bin/rclone ]; then
  TEMP=$(mktemp -d)
  (cd "$TEMP"
   curl -fsSLO https://downloads.rclone.org/v1.75.0/rclone-v1.75.0-linux-amd64.zip
   curl -fsSLO https://downloads.rclone.org/v1.75.0/SHA256SUMS
   sha256sum --check --ignore-missing SHA256SUMS >/dev/null
   unzip -q rclone-v1.75.0-linux-amd64.zip
   install -m 0755 rclone-v1.75.0-linux-amd64/rclone /opt/citas/bin/rclone)
  rm -rf "$TEMP"
fi
sudo -u ubuntu bash <<'AUTH' 
set -euo pipefail
umask 077
mkdir -p /home/ubuntu/.config/rclone /opt/citas/qlora
CONFIG=/home/ubuntu/.config/rclone/uniandes.conf
LOG=/opt/citas/qlora/auth-private.log
if [ -s "$CONFIG" ] && grep -q '^token = ' "$CONFIG"; then
  echo 'AUTH_CONFIG_EXISTS: comprobar acceso antes de volver a autorizar'
  exit 0
fi
if [ -s /opt/citas/qlora/auth.pid ] && kill -0 "$(cat /opt/citas/qlora/auth.pid)" 2>/dev/null; then
  echo 'AUTH_ALREADY_RUNNING'
else
  nohup env BROWSER=true timeout 1800 /opt/citas/bin/rclone config create uniandes onedrive config_is_local true config_type onedrive access_scopes 'Files.Read.All offline_access User.Read' --no-output --config "$CONFIG" >"$LOG" 2>&1 </dev/null &
  echo "$!" > /opt/citas/qlora/auth.pid
fi
python3 - <<'PY'
from pathlib import Path
import re,time
p=Path('/opt/citas/qlora/auth-private.log')
for _ in range(20):
 text=p.read_text() if p.exists() else ''
 match=re.search(r'http://127\.0\.0\.1:53682/auth[^\s]*',text)
 if match:
  print('AUTH_URL='+match.group(0))
  break
 time.sleep(.5)
else:
 print('AUTH_URL_PENDING: no se imprime el log privado')
 if 'unknown flag' in text: print('AUTH_ERROR_UNKNOWN_FLAG')
 if 'Failed to configure' in text: print('AUTH_ERROR_CONFIGURATION')
PY
AUTH
