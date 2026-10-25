#!/bin/sh
set -eu
install -d -m 700 /usr/local/lib/mhp /opt/mhp-backups/automatic
install -d -o 10001 -g 10001 -m 750 /opt/mhp-operations
install -d -o 10001 -g 10001 -m 750 /opt/mhp-operations/requests /opt/mhp-operations/results
install -m 700 /root/backup_worker.py /usr/local/lib/mhp/backup_worker.py
cat > /etc/systemd/system/mhp-operations.service <<'EOF'
[Unit]
Description=MHP backup and recovery requests
After=docker.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/mhp/backup_worker.py
EOF
cat > /etc/systemd/system/mhp-operations.timer <<'EOF'
[Unit]
Description=MHP operation queue check
[Timer]
OnBootSec=30
OnUnitInactiveSec=30
Unit=mhp-operations.service
[Install]
WantedBy=timers.target
EOF
cat > /etc/systemd/system/mhp-nightly-backup.service <<'EOF'
[Unit]
Description=MHP nightly backup
After=docker.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/mhp/backup_worker.py --scheduled
EOF
cat > /etc/systemd/system/mhp-nightly-backup.timer <<'EOF'
[Unit]
Description=MHP daily backup at 03:30 China time
[Timer]
OnCalendar=*-*-* 03:30:00 Asia/Shanghai
Persistent=true
Unit=mhp-nightly-backup.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now mhp-operations.timer mhp-nightly-backup.timer
systemctl start mhp-operations.service
