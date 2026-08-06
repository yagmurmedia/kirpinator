@echo off
cd /d "C:\Users\CanBEY\Desktop\kirpinator"
echo ==== %date% %time% : Starting Kirpinator server ==== >> logs\server.log
".venv\Scripts\python.exe" run.py >> logs\server.log 2>&1
echo ==== %date% %time% : Kirpinator server exited ==== >> logs\server.log
