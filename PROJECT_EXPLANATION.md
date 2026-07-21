# AI Smart Travel Planner - Project Explanation

## 1. Project Overview

AI Smart Travel Planner is a full-stack travel planning web application. It helps users create personalized trip itineraries by entering a destination, travel dates, budget, currency, number of travelers, interests, and travel style.

The application combines a React frontend with a FastAPI backend. The frontend collects trip details and displays itinerary results, while the backend handles itinerary generation, attraction search, weather lookup, file uploads, and optional trip history storage.

The project is designed to work with free OpenStreetMap data for maps and nearby places, alongside OpenWeather, Cloudinary, MongoDB, Firebase, Gemini, and OpenAI when those optional integrations are configured.

## 2. Main Purpose

The main goal of this project is to make travel planning easier by automatically generating a day-by-day itinerary. Instead of manually searching for attractions, weather, maps, and travel tips, the user can enter a destination and receive a structured plan.

The system supports:

- Destination-based itinerary generation
- Popular places selection
- Budget and currency-aware cost estimates
- Map display
- Weather information
- Travel document upload
- Trip history storage
- Optional AI-powered itinerary generation

## 3. Technology Stack

### Frontend

- React
- Vite
- JavaScript
- CSS
- Lucide React icons
- Firebase Authentication support
- Leaflet and OpenStreetMap tiles

### Backend

- Python
- FastAPI
- Pydantic
- Uvicorn
- HTTPX
- Motor for MongoDB
- Cloudinary SDK

### External Services

- Nominatim for destination geocoding
- Overpass API for tourist attractions and nearby places
- OpenWeather API for weather data
- Gemini API or OpenAI API for AI itinerary generation
- MongoDB Atlas for trip history
- Cloudinary for file uploads
- Firebase for authentication

## 4. Project Structure

```text
AI PLANNER/
+-- backend/
|   +-- app/
|   |   +-- main.py              # FastAPI routes
|   |   +-- models.py            # Pydantic request/response models
|   |   +-- config.py            # Environment settings
|   |   `-- services/
|   |       +-- ai.py            # AI and demo itinerary generation
|   |       +-- places.py        # Popular places search
|   |       +-- weather.py       # Weather lookup
|   |       +-- database.py      # MongoDB trip storage
|   |       `-- uploads.py       # Cloudinary upload handling
|   +-- main.py                  # Uvicorn main:app entry point
|   +-- requirements.txt         # Python dependencies
|   `-- .env                     # Backend environment variables
+-- src/
|   +-- App.jsx                  # Main React application
|   +-- PopularPlaces.jsx        # Popular places UI
|   +-- api.js                   # Trip/upload API calls
|   +-- placesService.js         # Places API client with frontend cache
|   +-- firebase.js              # Firebase auth helpers
|   +-- data.js                  # Static frontend options
|   +-- styles.css               # Application styles
|   `-- main.jsx                 # React entry point
+-- package.json                 # Root npm scripts and frontend deps
+-- README.md                    # Setup instructions
`-- PROJECT_EXPLANATION.md       # This document
```

## 5. How The Application Runs

The project is configured to run both frontend and backend using one command from the project root.

```bash
npm run dev
```

This command uses `concurrently` to start:

- React frontend with Vite at `http://localhost:5173`
- FastAPI backend with Uvicorn at `http://localhost:8000`

The browser opens automatically at:

```text
http://localhost:5173
```

The backend health check is available at:

```text
http://localhost:8000/health
```

## 6. Frontend Explanation

The frontend is responsible for the user interface. It allows the user to enter trip details, choose interests, select popular places, generate an itinerary, upload documents, and view trip history.

### Main Frontend File

`src/App.jsx` contains the main application layout and state.

It manages:

- Destination input
- Travel dates
- Budget and currency
- Travelers count
- Interests
- Travel style
- Notes
- Selected attractions
- Generated itinerary result
- Trip history
- Upload result

When the user clicks "Generate itinerary", the frontend sends the form data to the backend endpoint:

```text
POST /api/trips/generate
```

The response is shown in the result panel as:

- Trip summary
- Budget breakdown
- Map
- Day-by-day itinerary
- Packing tips
- Local tips

### Popular Places Component

`src/PopularPlaces.jsx` fetches and displays tourist attractions for the selected destination.

Each place card shows:

- Image if available
- Name
- Rating
- Review count if available
- Category
- Short description
- Checkbox selection

The component automatically selects fetched places so they can be used during itinerary generation. The user can also manually select or unselect places.

### Frontend Caching

`src/placesService.js` includes a simple in-memory cache. This prevents repeated calls for the same destination during the same browser session.

## 7. Backend Explanation

The backend is built with FastAPI. It receives requests from the frontend, validates data using Pydantic models, calls external services when configured, and returns structured JSON responses.

### Main API Routes

Defined in `backend/app/main.py`:

```text
GET  /health
POST /api/trips/generate
GET  /api/trips
GET  /api/places
GET  /api/places/photo
POST /api/uploads
```

### Health Route

```text
GET /health
```

Returns a simple response confirming that the backend is running.

### Trip Generation Route

```text
POST /api/trips/generate
```

Accepts the trip form data and returns a complete itinerary.

The backend validates:

- Destination
- Start and end date
- Budget
- Currency
- Travelers
- Interests
- Travel style
- Selected attractions

If the AI provider is configured, it can use Gemini or OpenAI. If not, it uses the built-in demo itinerary generator.

### Popular Places Route

```text
GET /api/places?destination=Paris
```

This route fetches popular tourist attractions.

The backend uses free OpenStreetMap services:

1. Geocodes the destination.
2. Uses Overpass to search nearby attractions, beaches, museums, restaurants, parks, viewpoints, historical places, and shopping areas.
3. Deduplicates and sorts places.
4. Returns up to 30 attractions.

No Google key or billing account is required. If Overpass is unavailable, the route returns an empty places list without failing the application.

### Photo Route

```text
GET /api/places/photo
```

The compatibility endpoint returns an unavailable response because OpenStreetMap does not provide a universal free place-photo service.

### Upload Route

```text
POST /api/uploads
```

Uploads travel documents or images to Cloudinary when Cloudinary credentials are configured.

### Trip History Route

```text
GET /api/trips
```

Returns saved trips from MongoDB when MongoDB is configured.

## 8. Data Models

The backend models are defined in `backend/app/models.py`.

Important models:

- `TripRequest`
- `TripPlan`
- `ItineraryDay`
- `ItineraryActivity`
- `SelectedAttraction`
- `PlaceResult`
- `PlacesResponse`
- `UploadResponse`

These models ensure that frontend and backend communicate using predictable data structures.

## 9. Itinerary Generation Flow

The itinerary generation flow works like this:

1. User enters trip details in the React form.
2. User selects popular places or keeps the auto-selected places.
3. Frontend sends the request to FastAPI.
4. Backend validates the request.
5. Backend fetches weather data if configured.
6. Backend generates the itinerary using AI or demo mode.
7. Backend calculates budget breakdown and estimated activity costs.
8. Backend saves the trip if MongoDB is configured.
9. Frontend displays the final itinerary.

## 10. Popular Places Flow

The popular places flow works like this:

1. User types a destination.
2. `PopularPlaces.jsx` calls `searchPlaces`.
3. `placesService.js` checks frontend cache.
4. If not cached, it calls:

```text
GET /api/places?destination=<destination>
```

5. Backend checks backend cache.
6. Nominatim resolves the destination and Overpass returns nearby places.
7. If Overpass is unavailable, it returns an empty list safely.
8. Frontend displays selectable cards.

## 11. Currency Handling

The app supports multiple currencies such as:

- USD
- INR
- EUR
- GBP

The backend stores the selected currency in the generated trip plan. The frontend formats budget values and activity costs using the selected currency.

This avoids hardcoded dollar signs and keeps the displayed values consistent with the user's selected currency.

## 12. Environment Configuration

Frontend environment variables are stored in:

```text
.env.local
```

Backend environment variables are stored in:

```text
backend/.env
```

Important backend variables:

```env
AI_PROVIDER=demo
GEMINI_API_KEY=
OPENAI_API_KEY=
MONGODB_URI=
OPENWEATHER_API_KEY=
GOOGLE_PLACES_API_KEY=
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

The app works without most keys using fallback/demo behavior. Real API keys enable live data.

## 13. Startup Commands

Install dependencies:

```bash
npm install
```

Run the full app:

```bash
npm run dev
```

Manual backend setup if the Python virtual environment is missing:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 14. Current Behavior

The current app can:

- Run frontend and backend together with one command
- Generate demo itineraries without AI keys
- Search OpenStreetMap places without a maps API key
- Format currency correctly
- Display maps
- Upload documents when Cloudinary is configured
- Save trip history when MongoDB is configured

## 15. Future Improvements

Possible future improvements include:

- Better image fallback for OpenStreetMap places
- More fallback attractions for additional cities
- Real-time exchange rates
- Drag-and-drop itinerary editing
- Hotel and transport recommendations
- User profile page
- Export itinerary as PDF
- Offline trip summary download
- Admin dashboard for API usage and saved trips

## 16. Conclusion

AI Smart Travel Planner is a complete full-stack travel planning application. It combines a modern React frontend with a FastAPI backend and optional external services. The project is flexible because it works in demo mode for development and can be upgraded with real API keys for production use.

The application provides a practical travel planning workflow: choose a destination, review popular places, generate an itinerary, view a map, check estimated costs, and save or revisit trips later.
