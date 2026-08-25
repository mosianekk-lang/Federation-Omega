FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production PORT=8080
COPY package.json ./
COPY server.mjs ./
COPY lib ./lib
USER node
EXPOSE 8080
CMD ["node", "server.mjs"]
