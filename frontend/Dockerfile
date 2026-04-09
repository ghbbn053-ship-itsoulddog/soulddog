FROM node:20-alpine

WORKDIR /app

# 安装依赖
COPY package.json package-lock.json* pnpm-lock.yaml* ./
RUN npm config set registry https://registry.npmmirror.com && \
    npm install -g pnpm && \
    pnpm config set registry https://registry.npmmirror.com && \
    pnpm install

# 复制代码
COPY . .

# 构建
RUN pnpm build

# 暴露端口
EXPOSE 3000

# 启动
CMD ["pnpm", "start"]
