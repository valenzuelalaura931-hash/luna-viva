Add-Type -AssemblyName System.Drawing

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pngPath = Join-Path $projectDir "public\img\Logo luna sin fondo.png"
$icoPath = Join-Path $projectDir "assets\icon.ico"
$htmlPath = Join-Path $projectDir "index.html"

# 1. Generar archivo .ico de alta calidad
try {
    $bmp = [System.Drawing.Bitmap]::FromFile($pngPath)
    $thumb = New-Object System.Drawing.Bitmap($bmp, 128, 128)
    $iconHandle = $thumb.GetHicon()
    $icon = [System.Drawing.Icon]::FromHandle($iconHandle)
    $fs = New-Object System.IO.FileStream($icoPath, [System.IO.FileMode]::Create)
    $icon.Save($fs)
    $fs.Close()
    $thumb.Dispose()
    $bmp.Dispose()
    Write-Host "Icono generado en: $icoPath"
} catch {
    Write-Host "Advertencia al generar icono: $_"
}

# 2. Localizar navegador óptimo (Edge o Chrome con modo aplicación)
$browserExe = ""
$argsPrefix = ""

if (Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe") {
    $browserExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    $profileArg = ""
    if (Test-Path "$env:LOCALAPPDATA\Google\Chrome\User Data\Profile 2") {
        $profileArg = "--profile-directory=""Profile 2"" "
    }
    $argsPrefix = "$($profileArg)--app=""file:///$($htmlPath.Replace('\', '/'))"""
} elseif (Test-Path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") {
    $browserExe = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    $argsPrefix = "--app=""file:///$($htmlPath.Replace('\', '/'))"""
} else {
    $browserExe = $htmlPath
    $argsPrefix = ""
}

# 3. Crear acceso directo en el Escritorio (Desktop)
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Luna Viva - Inventario.lnk"

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $browserExe
if ($argsPrefix -ne "") {
    $shortcut.Arguments = $argsPrefix
}
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description = "Luna Viva - Sistema de Control de Inventario y Stock"
if (Test-Path $icoPath) {
    $shortcut.IconLocation = "$icoPath, 0"
}
$shortcut.Save()

Write-Host "Acceso directo creado en el Escritorio: $shortcutPath"

# 4. Crear también un acceso directo dentro de la carpeta del proyecto
$localShortcutPath = Join-Path $projectDir "Luna Viva - Inventario.lnk"
$localShortcut = $wshShell.CreateShortcut($localShortcutPath)
$localShortcut.TargetPath = $browserExe
if ($argsPrefix -ne "") {
    $localShortcut.Arguments = $argsPrefix
}
$localShortcut.WorkingDirectory = $projectDir
$localShortcut.Description = "Luna Viva - Sistema de Control de Inventario y Stock"
if (Test-Path $icoPath) {
    $localShortcut.IconLocation = "$icoPath, 0"
}
$localShortcut.Save()

Write-Host "Acceso directo local creado en: $localShortcutPath"
