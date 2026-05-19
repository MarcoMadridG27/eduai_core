@echo off
echo Iniciando el escaneo de SonarQube usando Docker...
echo Asegurate de que el servidor local de SonarQube este corriendo en http://localhost:9000

:: Buscar SONAR_TOKEN en el archivo .env
set SONAR_TOKEN=
for /f "usebackq tokens=1,2 delims==" %%i in (".env") do (
    if "%%i"=="SONAR_TOKEN" set SONAR_TOKEN=%%j
)

if "%SONAR_TOKEN%"=="" (
    echo [ERROR] No se encontro la variable SONAR_TOKEN en el archivo .env.
    echo Asegurate de definir SONAR_TOKEN en tu archivo .env.
    pause
    exit /b 1
)

docker run --rm ^
    -e SONAR_HOST_URL="http://host.docker.internal:9000" ^
    -e SONAR_TOKEN="%SONAR_TOKEN%" ^
    -v "%cd%:/usr/src" ^
    sonarsource/sonar-scanner-cli

echo Escaneo finalizado. Revisa los resultados en http://localhost:9000
pause
