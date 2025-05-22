@echo off

for /f %%i in ('docker compose ps --status running --format "{{.Name}}"') do (
    set container_running=1
    goto :proceed
)

:proceed
if defined container_running (
    goto :shutdown
) else (
    goto :startup
)

:startup
echo Available ENV files:
for %%f in (*.env*) do echo   - %%f

echo.
set /p envfile=Which ENV file do you want to use? 
if not exist "%envfile%" (
    echo Error: File "%envfile%" not found.
    exit /b 1
)
set ENV_FILE=%envfile%

echo.
set /p build=Do you want to force a build first (y/N)?
echo.
 
if /i "%build%"=="y" (
    call cli/build-startup.bat %ENV_FILE%
) else (
    call cli/startup.bat %ENV_FILE%
)

exit /b

:shutdown
call cli/shutdown.bat

exit /b