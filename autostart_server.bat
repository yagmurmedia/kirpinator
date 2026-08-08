@echo off
cd /d "C:\Users\CanBEY\Desktop\kirpinator"

REM This GPU (GTX 1060) can't run Ollama's CUDA backend — forced to CPU.
REM The pipeline's auto topic-protection (protected_moments.py) needs Ollama
REM up, so it's started here alongside the server rather than relying on it
REM having been left running manually.
set OLLAMA_LLM_LIBRARY=cpu
echo ==== %date% %time% : Starting Ollama (CPU mode) ==== >> logs\server.log
start "" /min "C:\Users\CanBEY\AppData\Local\Programs\Ollama\ollama.exe" serve >> logs\ollama.log 2>&1

echo ==== %date% %time% : Starting Kirpinator server ==== >> logs\server.log
".venv\Scripts\python.exe" run.py >> logs\server.log 2>&1
echo ==== %date% %time% : Kirpinator server exited ==== >> logs\server.log
