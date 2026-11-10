@echo off
title Luna Viva - Servidor de Inventario
color 0D
echo ========================================================
echo           LUNA VIVA - SISTEMA DE INVENTARIO
echo       Boutique de Belleza, Resplandor & Vitalidad
echo ========================================================
echo.
echo Iniciando servidor local en el puerto 8080...
echo.

cd /d "%~dp0"

:: Abrir navegador en http://localhost:8080
start http://localhost:8080

:: Iniciar servidor Python con auto-guardado en disco
python server.py 8080

pause
