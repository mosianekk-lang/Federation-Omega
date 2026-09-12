FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production PORT=8080
COPY package.json ./
RUN npm install --omit=dev --ignore-scripts
COPY src ./src
USER node
EXPOSE 8080
CMD ["node", "src/server.js"]
