FROM node:22-alpine

ENV NODE_ENV=production PORT=8080
WORKDIR /app
COPY package.json ./
COPY src ./src
USER node
CMD ["node", "src/server.js"]
