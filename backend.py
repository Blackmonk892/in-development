from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import requests
setattr
from math import radians, sin, cos, sqrt, atan2
from pydantic import BaseModel
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
CSV_PATH = r"C:\Users\xoxo3\OneDrive\Desktop\New folder\bloodbank\blood_banks.csv"  
GRAPHHOPPER_KEY = os.getenv("GRAPHHOPPER_API_KEY", "9e9f9e52-ce51-4f10-b4e4-f3fd74b63123")  # Defaults to empty string if not set

# Mapping from our model fields to the CSV column headers (after stripping)
col_mapping = {
    'id': 'Sr No',
    'name': 'Blood Bank Name',
    'address': 'Address',
    'city': 'City',
    'state': 'State',
    'latitude': 'latitude',
    'longitude': 'longitude'
}

class Location(BaseModel):
    latitude: float
    longitude: float

class BloodBank(BaseModel):
    id: str
    name: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    distance: float = None


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371 
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (sin(dlat/2) ** 2 +
         cos(radians(lat1)) * cos(radians(lat2)) *
         sin(dlon/2) ** 2)
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

def load_blood_banks():
    try:
        logger.info(f"Attempting to load CSV from: {CSV_PATH}")
        if not os.path.exists(CSV_PATH):
            raise FileNotFoundError(f"CSV file not found at {CSV_PATH}")
        
        
        df = pd.read_csv(CSV_PATH, encoding="windows-1252")
        df.columns = df.columns.str.strip()
        logger.info(f"Successfully loaded CSV with {len(df)} records")
        
        
        missing_cols = [col for col in col_mapping.values() if col not in df.columns]
        if missing_cols:
            raise ValueError(f"CSV missing required columns: {', '.join(missing_cols)}")
        
        
        df['Address'] = df['Address'].fillna("")
        df['City'] = df['City'].fillna("")
        
        banks = []
        for _, row in df.iterrows():
            try:
                bank = BloodBank(
                    id=str(row[col_mapping['id']]),
                    name=row[col_mapping['name']],
                    address=row[col_mapping['address']],
                    city=row[col_mapping['city']],
                    state=row[col_mapping['state']],
                    latitude=float(row[col_mapping['latitude']]),
                    longitude=float(row[col_mapping['longitude']])
                )
                banks.append(bank)
            except Exception as inner_e:
                logger.warning(f"Skipping row due to error: {inner_e}")
        return banks
    except Exception as e:
        logger.error(f"Error loading blood banks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CSV Error: {str(e)}")

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Blood Bank API!"}


@app.post("/nearby")
async def get_nearby(location: Location):
    try:
        logger.info(f"Searching nearby blood banks for location: {location.latitude}, {location.longitude}")
        banks = load_blood_banks()
        for bank in banks:
            bank.distance = haversine(
                location.latitude,
                location.longitude,
                bank.latitude,
                bank.longitude
            )
       
        return sorted(banks, key=lambda x: x.distance)[:10]
    except Exception as e:
        logger.error(f"Error in nearby endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/all-blood-banks")
async def get_all_blood_banks():
    """Return all blood banks without distance calculation"""
    try:
        logger.info("Fetching all blood banks")
        return load_blood_banks()
    except Exception as e:
        logger.error(f"Error fetching all blood banks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/route")
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    try:
        logger.info(f"Getting route from ({start_lat},{start_lon}) to ({end_lat},{end_lon})")
        if not GRAPHHOPPER_KEY:
            logger.warning("Graphhopper API key not set")
            raise HTTPException(status_code=500, detail="Graphhopper API key not configured")
        
        url = "https://graphhopper.com/api/1/route"
        params = {
            "point": [f"{start_lat},{start_lon}", f"{end_lat},{end_lon}"],
            "vehicle": "car",
            "key": GRAPHHOPPER_KEY,
            "points_encoded": "false"
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Graphhopper API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Routing API error: {str(e)}")
    except Exception as e:
        logger.error(f"Route calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)
