@echo off
cd /d d:\SOLO-13\021-bci-signal-decode\backend
echo Starting BCI backend service... > start_log.txt
echo Time: %date% %time% >> start_log.txt
python -u quick_start.py >> start_log.txt 2>&1
