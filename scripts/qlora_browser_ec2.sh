#!/bin/bash
# Escritorio temporal accesible solo por túnel SSM; no abre puertos públicos.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y xvfb x11vnc novnc websockify dbus-x11 gnupg xdg-utils >/opt/citas/qlora/browser-install.log 2>&1
# El paquete Snap no puede ejecutarse desde esta sesión SSM. Usar DEB oficial,
# firmado por Mozilla, sin desactivar el sandbox del navegador.
if [ ! -f /opt/citas/qlora/mozilla-deb.ready ]; then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://packages.mozilla.org/apt/repo-signing-key.gpg -o /etc/apt/keyrings/packages.mozilla.org.asc
  FINGERPRINT=$(gpg --show-keys --with-colons /etc/apt/keyrings/packages.mozilla.org.asc 2>/dev/null | awk -F: '$1=="fpr" && !seen {print $10; seen=1}')
  test "$FINGERPRINT" = 35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3
  echo 'deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main' > /etc/apt/sources.list.d/mozilla.list
  printf 'Package: firefox*\nPin: origin packages.mozilla.org\nPin-Priority: 1001\n' > /etc/apt/preferences.d/mozilla
  apt-get update -qq
  VERSION=$(apt-cache madison firefox | awk '/packages.mozilla.org/ && !seen {print $3; seen=1}')
  test -n "$VERSION"
  apt-get install -y --allow-downgrades "firefox=$VERSION" >>/opt/citas/qlora/browser-install.log 2>&1
  touch /opt/citas/qlora/mozilla-deb.ready
fi
sudo -u ubuntu bash <<'BROWSER_SETUP'
set -euo pipefail
umask 077
mkdir -p /opt/citas/qlora /home/ubuntu/Downloads/qlora /home/ubuntu/.mozilla/qlora-profile
chmod 700 /opt/citas/qlora /home/ubuntu/Downloads/qlora /home/ubuntu/.mozilla/qlora-profile
PROFILE=/home/ubuntu/.mozilla/qlora-profile
cat > "$PROFILE/user.js" <<'PREFS'
user_pref("browser.download.folderList", 2);
user_pref("browser.download.dir", "/home/ubuntu/Downloads/qlora");
user_pref("browser.download.useDownloadDir", true);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.aboutwelcome.enabled", false);
PREFS
if ! pgrep -u ubuntu -f '^Xvfb :99 ' >/dev/null; then
  nohup Xvfb :99 -screen 0 1280x900x24 -nolisten tcp >/opt/citas/qlora/xvfb.log 2>&1 </dev/null &
fi
for i in $(seq 1 20); do test -S /tmp/.X11-unix/X99 && break; sleep 1; done
if ! pgrep -u ubuntu -f '^x11vnc -display :99' >/dev/null; then
  nohup x11vnc -display :99 -localhost -listen 127.0.0.1 -rfbport 5900 -forever -shared -nopw >/opt/citas/qlora/vnc.log 2>&1 </dev/null &
fi
if ! pgrep -u ubuntu -f 'websockify.*127.0.0.1:6080' >/dev/null; then
  nohup websockify --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900 >/opt/citas/qlora/websockify.log 2>&1 </dev/null &
fi
if ! pgrep -u ubuntu -f 'firefox.*qlora-profile' >/dev/null; then
  nohup env DISPLAY=:99 dbus-run-session -- firefox --no-remote --profile "$PROFILE" --new-window https://uniandes-my.sharepoint.com/ >/opt/citas/qlora/firefox-private.log 2>&1 </dev/null &
fi
python3 - <<'PY'
import socket,time,json,subprocess
for _ in range(30):
 try:
  with socket.create_connection(('127.0.0.1',6080),timeout=2):pass
  if subprocess.run(['pgrep','-u','ubuntu','-x','firefox'],stdout=subprocess.DEVNULL).returncode: raise OSError('Firefox aún no está listo')
  print(json.dumps({'viewer_ready':True,'viewer_port':6080,'downloads':'/home/ubuntu/Downloads/qlora','public_ports_opened':False}))
  break
 except OSError:time.sleep(1)
else:raise SystemExit('VIEWER_NOT_READY')
PY
BROWSER_SETUP
