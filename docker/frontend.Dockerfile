FROM node:20-alpine

WORKDIR /app

# Install dependencies based on the preferred package manager
COPY apps/frontend/package.json apps/frontend/package-lock.json* ./

# Check if lockfile exists to avoid failing npm ci
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY apps/frontend .

# Next.js telemetry
ENV NEXT_TELEMETRY_DISABLED 1

EXPOSE 3000

CMD ["npm", "run", "dev"]
