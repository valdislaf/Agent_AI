# Auto-elevate and run python agent
# Автоматическое повышение прав и запуск Python агента

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Важно: переходим в папку скрипта, чтобы Python видел файлы рядом
Set-Location $scriptDir 

# --- 1. ПРОВЕРКА АДМИНА / CHECK ADMIN ---
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $admin) {
    # Перезапуск этого же скрипта с правами администратора
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# --- 2. ЗАПУСК PYTHON / RUN PYTHON ---
$pyScript = "win_agent.py"

if (Test-Path $pyScript) {
    # Аналог вашего echo 'АГЕНТ 777'
    Write-Host "АГЕНТ 777" -ForegroundColor Cyan

    # Запуск Python скрипта
    # Мы находимся в папке скрипта, поэтому просто вызываем его
    try {
        python $pyScript
    } catch {
        # Если python не установлен или не в PATH
        if ($PSUICulture.Name -match "^ru") {
            Write-Host "Ошибка: Не удалось запустить Python. Проверьте, установлен ли он и добавлен ли в PATH." -ForegroundColor Red
        } else {
            Write-Host "Error: Failed to run Python. Check if it is installed and added to PATH." -ForegroundColor Red
        }
    }
} else {
    # Если win_agent.py не найден
    if ($PSUICulture.Name -match "^ru") {
        Write-Host "Файл $pyScript не найден в каталоге $scriptDir" -ForegroundColor Red
    } else {
        Write-Host "File $pyScript not found in directory $scriptDir" -ForegroundColor Red
    }
}

# --- 3. ПАУЗА / PAUSE ---
# Аналог команды pause, чтобы окно не закрылось сразу
Write-Host "" # Пустая строка для отступа
if ($PSUICulture.Name -match "^ru") {
    Read-Host "Нажмите Enter для выхода..."
} else {
    Read-Host "Press Enter to exit..."
}