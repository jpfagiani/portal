#!/bin/bash
# Remove o serviço do portal. O banco (dados.db) e as imagens enviadas
# são PRESERVADOS em /opt/portal — apague a pasta manualmente se quiser.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Execute como root:  sudo ./desinstalar.sh"; exit 1; }

systemctl disable --now portal.service 2>/dev/null || true
systemctl disable --now portal-nome.service 2>/dev/null || true
rm -f /etc/systemd/system/portal.service /etc/systemd/system/portal-nome.service
rm -f /usr/local/bin/portal-anuncia-nome

# Nomes usados até a versão 1.1, quando o serviço rodava em /opt/intranet.
systemctl disable --now intranet.service 2>/dev/null || true
systemctl disable --now intranet-nome.service 2>/dev/null || true
rm -f /etc/systemd/system/intranet.service /etc/systemd/system/intranet-nome.service
rm -f /usr/local/bin/intranet-anuncia-nome

sed -i '/# portal-intranet$/d' /etc/hosts 2>/dev/null || true
systemctl daemon-reload

echo "Serviço removido. Dados preservados em /opt/portal"
echo "Para apagar tudo:  rm -rf /opt/portal && userdel portal"
if [ -d /opt/intranet ]; then
    echo
    echo "Sobrou também a pasta da instalação antiga: /opt/intranet"
    echo "  rm -rf /opt/intranet && userdel intranet"
fi
