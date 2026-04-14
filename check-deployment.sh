#!/bin/bash
# 部署检查脚本 - 验证所有服务是否正常运行

echo "========================================="
echo "🔍 校园AI助手 - 部署检查"
echo "========================================="
echo ""

# 1. 检查Docker容器状态
echo "📦 1. 检查Docker容器状态..."
docker-compose ps
echo ""

# 2. 拉取最新代码
echo "📥 2. 拉取最新代码..."
git pull origin main
echo ""

# 3. 重启后端服务
echo "🔄 3. 重启后端服务..."
docker-compose restart backend
sleep 3
echo ""

# 4. 查看后端日志（最后50行）
echo "📋 4. 查看后端日志（最后50行）..."
docker-compose logs --tail=50 campus-ai-backend
echo ""

# 5. 检查关键日志
echo "========================================="
echo "🎯 5. 关键日志检查..."
echo "========================================="

echo ""
echo "✅ 检查编码修复："
docker-compose logs campus-ai-backend | grep "【编码】" | tail -5

echo ""
echo "✅ 检查登录成功："
docker-compose logs campus-ai-backend | grep "登录成功" | tail -3

echo ""
echo "✅ 检查培养方案解析："
docker-compose logs campus-ai-backend | grep "【培养方案】" | tail -5

echo ""
echo "✅ 检查成绩解析："
docker-compose logs campus-ai-backend | grep "成功获取.*条成绩记录" | tail -3

echo ""
echo "✅ 检查课表解析："
docker-compose logs campus-ai-backend | grep "成功获取.*条课表记录" | tail -3

echo ""
echo "✅ 检查向量化："
docker-compose logs campus-ai-backend | grep "【向量化】" | tail -10

echo ""
echo "========================================="
echo "🎉 检查完成！"
echo "========================================="
echo ""
echo "💡 提示："
echo "  - 如果培养方案显示 '共 109 门课程' 说明修复成功"
echo "  - 如果看到 '共 21 门课程' 说明还是旧代码，需要重新git pull"
echo "  - 持续查看日志: docker-compose logs -f campus-ai-backend"
echo ""
