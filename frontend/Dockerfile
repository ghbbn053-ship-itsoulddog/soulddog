# 开发模式 Dockerfile（保留热更新）
FROM node:20-alpine

WORKDIR /app

# 安装系统依赖
RUN apk add --no-cache libc6-compat

# 安装 pnpm
RUN npm config set registry https://registry.npmmirror.com && \
    npm install -g pnpm && \
    pnpm config set registry https://registry.npmmirror.com

# 先复制依赖文件
COPY package.json pnpm-lock.yaml* ./

# 安装依赖（会写入镜像层）
RUN pnpm install --frozen-lockfile

# 复制所有代码
COPY . .

# 暴露端口
EXPOSE 3000

# 启动开发服务器（支持热更新）
CMD ["pnpm", "dev", "-p", "3000"]
