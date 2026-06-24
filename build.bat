@echo off
chcp 65001 >nul
echo ============================================
echo   智能出卷系统 - 一键打包脚本
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请安装 Python 3.10+
    pause & exit /b 1
)

:: 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请从 https://nodejs.org 安装
    pause & exit /b 1
)

echo [1/5] 安装 Python 依赖...
pip install -r requirements.txt -q
if errorlevel 1 ( echo [错误] pip install 失败 & pause & exit /b 1 )

echo [2/5] 安装 Node.js 依赖...
cd docx_gen
npm install --prefer-offline -q
if errorlevel 1 ( echo [错误] npm install 失败 & pause & exit /b 1 )
cd ..

echo [3/5] 安装 PyInstaller...
pip install pyinstaller -q

echo [4/5] 开始打包 (可能需要 3~8 分钟)...
pyinstaller exam_generator.spec --clean --noconfirm
if errorlevel 1 ( echo [错误] 打包失败，请查看上方错误信息 & pause & exit /b 1 )

echo [5/5] 打包完成！
echo.
echo 输出目录: dist\智能出卷系统\
echo 主程序:   dist\智能出卷系统\智能出卷系统.exe
echo.
explorer dist\智能出卷系统
pause
