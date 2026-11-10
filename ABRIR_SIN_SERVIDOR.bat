@echo off
:: Abre el sistema de inventario de Luna Viva directamente en el navegador sin necesidad de servidor
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --profile-directory="Profile 2" --app="file:///%~dp0index.html"
) else (
    start "" "%~dp0index.html"
)
exit
