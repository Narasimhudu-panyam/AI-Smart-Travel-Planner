# ✈️ AI Smart Travel Planner

An AI-powered travel planning application that generates personalized travel itineraries based on destination, budget, travel duration, and preferences using Google Gemini AI.

## 🌐 Live Demo

Frontend:
https://ai-smart-travel-planner-five.vercel.app

Backend API:
https://ai-smart-travel-planner-1ji3.onrender.com

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

## Vercel + Render deployment

In Vercel, set the following **Production** environment variables before rebuilding the frontend:

```text
VITE_API_BASE_URL=https://<your-render-service>.onrender.com
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
VITE_FIREBASE_MEASUREMENT_ID=...
```

In Render, set these backend environment variables. `FRONTEND_ORIGIN` is an explicit comma-separated CORS allowlist; use the real Vercel domain, not a wildcard.

```text
FRONTEND_ORIGIN=https://<your-vercel-project>.vercel.app
MONGODB_URI=...
GEMINI_API_KEY=...
GOOGLE_MAPS_API_KEY=...
```

The deployed backend uses the health endpoint at `https://<your-render-service>.onrender.com/health` and API routes under `/api`.

For Firebase, add the Vercel domain in **Firebase Console → Authentication → Settings → Authorized domains**. Enable both the Email/Password and Google providers in **Authentication → Sign-in method**. The Vercel deployment does not need Firebase secrets beyond the public `VITE_FIREBASE_*` web configuration values.

The backend uses `GOOGLE_MAPS_API_KEY` exclusively for server-side Geocoding and the Places API (New). In Google Cloud Console, enable **Geocoding API** and **Places API (New)**, attach billing, and ensure the key's API restrictions permit both APIs. Because requests originate from Render, do not restrict this server-side key with browser HTTP-referrer restrictions; use a separately restricted browser key if one is ever needed.

## API Keys

The app works without keys using demo data. Add real keys to enable live AI, weather, database history, maps, and uploads.

## Docker

Keep secrets in `backend/.env` and do not commit that file. Start the production containers with:

```bash
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend health check: `http://localhost:8000/health`
