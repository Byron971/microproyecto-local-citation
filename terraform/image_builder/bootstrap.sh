#!/bin/bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io git make python3 python3-venv python3-pip unzip curl rclone
systemctl enable --now docker
usermod -aG docker ubuntu
# Ubuntu incluye SSM Agent como snap; no se abren puertos SSH.
snap start amazon-ssm-agent
install -d -o ubuntu -g ubuntu -m 0750 /opt/citas
# Limita el tiempo encendido; los discos siguen existiendo hasta retirar con Terraform.
shutdown -h +180
printf 'Builder preparado; apagado automático en tres horas.\n' > /opt/citas/READY
