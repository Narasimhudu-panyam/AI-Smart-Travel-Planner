# AI Smart Travel Planner

A cloud-ready intelligent trip planning system using React, FastAPI, Generative AI, Firebase Authentication, cloud database storage, Cloudinary uploads, Google Maps, and OpenWeather.

## Features

- Personalized itinerary generation from destination, dates, budget, group size, travel style, and interests
- FastAPI backend with Gemini/OpenAI integration and a demo fallback generator
- Optional MongoDB Atlas persistence for trip history
- Optional Cloudinary document/image uploads
- Optional OpenWeather weather lookup
- Firebase Authentication-ready frontend
- Google Maps embed-ready frontend
- Deployment-friendly structure for Vercel and Render

## Project Structure

```text
.
+-- backend/             # FastAPI API server
+-- src/                 # React frontend
+-- package.json         # Root scripts for frontend and backend
`-- .env.example         # Frontend environment sample
```

## Run The App

```bash
npm install
npm run dev
```

This starts both services in one terminal:

- React frontend: `http://localhost:5173`
- FastAPI backend: `http://localhost:8000`

The browser opens automatically at `http://localhost:5173`. Press `Ctrl+C` in the terminal to stop both services together.

`npm start` runs the same command as `npm run dev`.

## First-Time Backend Setup

If the backend virtual environment is missing, create it once before running the app:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The root npm backend script starts FastAPI with `uvicorn main:app --reload`.

## Environment

Copy `.env.example` to `.env.local` and add your Firebase and Google Maps keys when ready.

Copy `backend/.env.example` to `backend/.env` and add keys for Gemini/OpenAI, MongoDB Atlas, Cloudinary, and OpenWeather.

## API Keys

The app works without keys using demo data. Add real keys to enable live AI, weather, database history, maps, and uploads.

## Docker

Keep secrets in `backend/.env` and do not commit that file. Start the production containers with:

```bash
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend health check: `http://localhost:8000/health`

## AWS deployment readiness

The root `Dockerfile` has a `backend` target that reads the standard `PORT` environment variable, making it suitable for an AWS App Runner image deployment. Build and push that target to ECR, then configure App Runner with the required environment variables: `MONGODB_URI`, `GEMINI_API_KEY`, `GOOGLE_MAPS_API_KEY`, `FRONTEND_ORIGIN`, and any optional weather/upload credentials. Deploy the `frontend` target separately (for example, through CloudFront/S3) or keep both services together with Docker Compose on a container platform.
