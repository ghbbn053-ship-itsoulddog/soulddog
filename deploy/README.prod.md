# 生产部署（网关代理 + SSE）

## 1. 准备环境变量

在项目根目录创建 `.env.prod`（最少）：

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=campus_ai
QWEN_API_KEY=your_qwen_key
QWEN_MODEL=qwen-plus
JWT_SECRET_KEY=replace_with_random_string
EDUCATION_SYSTEM_URL=http://jwxt.gdufe.edu.cn/jsxsd/
```

## 2. 启动生产栈

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

## 3. 验证

```bash
curl -i http://127.0.0.1/api/health
docker compose -f docker-compose.prod.yml logs -f gateway backend frontend
```

## 4. 说明

- 外部入口统一走 `gateway`（80端口）。
- `/api/chat/send-stream` 在 `deploy/nginx/prod.conf` 中已禁缓冲，支持稳定流式输出。
- 不要把开发用的 `docker-compose.yml` 和生产用的 `docker-compose.prod.yml` 混用。

