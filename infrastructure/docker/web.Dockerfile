FROM node:20-slim

WORKDIR /srv/apps/web
COPY apps/web/package.json ./
RUN npm install
COPY apps/web .

EXPOSE 3000
CMD ["npm", "run", "dev"]
