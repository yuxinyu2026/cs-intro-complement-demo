@echo off
chcp 65001 >nul
set "PATH=C:\Users\admin\Downloads\_tools\PortableGit\cmd;%PATH%"
cd /d "%~dp0"
echo Git ?????????%CD%
git --version
cmd /k
