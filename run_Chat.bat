@echo off
echo AGENT 777
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%OLLAMA_EXE%" (
  powershell -NoProfile -Command "if (-not (Get-Process -Name ollama -ErrorAction SilentlyContinue)) { Start-Process -WindowStyle Hidden -FilePath '%OLLAMA_EXE%' -ArgumentList 'serve --context-window 8192' }"
) else (
  echo ollama.exe not found in %LOCALAPPDATA%\Programs\Ollama
)
python .\chat_ollama.py
pause
