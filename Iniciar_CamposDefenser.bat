@echo off
cd /d "%~dp0"

:: Garante que o logo.ico exista antes de criar o atalho
if not exist "%~dp0logo.ico" (
    python -c "from PIL import Image; Image.open('logo.png').save('logo.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
)

:: Cria o atalho oficial na Area de Trabalho com a logo do Campos Defenser
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Campos Defenser.lnk'); $s.TargetPath='pythonw.exe'; $s.Arguments='\"%~dp0main.py\"'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0logo.ico'; $s.Save()"

:: Inicia o Campos Defenser imediatamente
start "" pythonw "%~dp0main.py"