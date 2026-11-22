#!/bin/bash
# Escritorio temporal accesible solo por túnel SSM; no abre puertos públicos.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y xvfb x11vnc novnc websockify dbus-x11 firefox >/opt/citas/qlora/browser-install.log 2>&1
sudo -u ubuntu bash <<'BROWSER_SETUP'
set -euo pipefail
umask 077
mkdir -p /opt/citas/qlora /home/ubuntu/Downloads/qlora /home/ubuntu/snap/firefox/common/qlora-profile
chmod 700 /opt/citas/qlora /home/ubuntu/Downloads/qlora /home/ubuntu/snap/firefox/common/qlora-profile
PROFILE=/home/ubuntu/snap/firefox/common/qlora-profile
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
import socket,time,json
for _ in range(30):
 try:
  with socket.create_connection(('127.0.0.1',6080),timeout=2):pass
  print(json.dumps({'viewer_ready':True,'viewer_port':6080,'downloads':'/home/ubuntu/Downloads/qlora','public_ports_opened':False}))
  break
 except OSError:time.sleep(1)
else:raise SystemExit('VIEWER_NOT_READY')
PY
BROWSER_SETUP
