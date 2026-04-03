@echo off
chcp 65001
echo ==========================================
echo 正在执行一键同步：抽取脱敏数据 ^& 拷贝最新前端代码
echo ==========================================

python "%~dp0generate_demo_data.py"

echo.
echo ==========================================
echo 准备推送至 GitHub Demo 仓库...
echo ==========================================

cd /d "E:\Pacemaker_Dashboard_Demo"
git add .
git commit -m "auto-sync: 自动同步最新前端代码及脱敏数据"
git push origin master

echo.
echo ==========================================
echo 🎉 同步成功！GitHub Pages 将在 1-2 分钟内自动刷新。
echo 请按任意键退出...
pause > nul
