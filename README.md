# DeepInsight OS

Production-ready SaaS foundation for an AI-powered operating system for marketing agencies.

## Architecture

This project is a monorepo containing:
- `apps/frontend`: Next.js 15, React, TailwindCSS, shadcn/ui.
- `apps/backend`: FastAPI, SQLAlchemy, Alembic, PostgreSQL.
- `docker/`: Dockerfiles for local development and deployment.

## Prerequisites

- Docker and Docker Compose
- Node.js 20+
- Python 3.11+

## Getting Started

### Environment Variables

Set up your `.env` files in both frontend and backend based on `.env.example` (or use the provided defaults).
You will need a Clerk Publishable Key and Secret Key for authentication to work.

### Running Locally with Docker

You can run the entire stack using a single command:

```bash
docker-compose up --build
```

- Frontend will be available at `http://localhost:3000`
- Backend API will be available at `http://localhost:8000`
- API documentation (Swagger) at `http://localhost:8000/docs`
- PostgreSQL at `localhost:5432`

## Project Structure

- `apps/frontend`: Contains the App Router, Authentication, Dashboard UI.
- `apps/backend`: Contains the REST API, Database Models, Schemas, Services.

## Tech Stack
- **Frontend**: Next.js 15, TypeScript, TailwindCSS, shadcn/ui, Clerk
- **Backend**: FastAPI, Python, SQLAlchemy, Alembic
- **Database**: PostgreSQL
- **DevOps**: Docker, GitHub Actions
