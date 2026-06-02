from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
)

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS coordinates in miles"""
    R = 3959  # Earth's radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def find_closest_gauge(lat, lng):
    """Find the flood gauge closest to the user's address"""
    # Updated working URL with all region IDs
    url = "https://www.harriscountyfws.org/Home/GetSiteRecentData?regionId=3&regionId=24&regionId=25&regionId=26&regionId=21&regionId=4&regionId=10&regionId=22&regionId=1&regionId=14&regionId=18&regionId=19&regionId=23&regionId=20&timeSpan=7&dt=1779069600000"
    headers = {"Referer": "https://www.harriscountyfws.org/"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
    except Exception as e:
        return None, float('inf')
    
    closest = None
    closest_distance = float('inf')
    
    # Safe iteration with error handling
    for site in data.get("features", []):
        try:
            props = site.get("properties", {})
            geometry = site.get("geometry", {})
            coords = geometry.get("coordinates", [0, 0])
            
            # Validate coordinates exist
            if len(coords) < 2:
                continue
            
            # Safely convert coordinates to float
            try:
                gauge_lng = float(coords[0])
                gauge_lat = float(coords[1])
            except (ValueError, TypeError):
                continue
            
            distance = haversine(lat, lng, gauge_lat, gauge_lng)
            
            if distance < closest_distance:
                closest_distance = distance
                closest = props
        except Exception:
            continue
    
    return closest, closest_distance

def calculate_risk_from_gauge(gauge, distance_miles):
    """Calculate risk tier and score from gauge data"""
    # Safely extract data with checks
    try:
        stream_data = gauge.get("StreamData", [])
        if not stream_data:
            return "UNKNOWN", 0, 0, 0, 0, distance_miles
        
        stream = stream_data[0]
        current = stream.get("CurrentLevel", 0)
        
        channel_info = stream.get("ChannelInfo", {})
        flood = channel_info.get("FloodLevelIndicator")
        
        if flood is None or flood == 999:
            return "UNKNOWN", 0, 0, 0, 0, distance_miles
        
        buffer = flood - current
        
        if buffer <= 0:
            tier = "CRITICAL"
            score = 95
        elif buffer <= 2:
            tier = "HIGH"
            score = 75
        elif buffer <= 5:
            tier = "MEDIUM"
            score = 50
        elif buffer <= 10:
            tier = "LOW"
            score = 25
        else:
            tier = "SAFE"
            score = 10
        
        return tier, score, buffer, current, flood, distance_miles
    except Exception:
        return "UNKNOWN", 0, 0, 0, 0, distance_miles

@app.get("/risk")
def get_risk(address: str = Query(...), lat: float = Query(...), lng: float = Query(...)):
    """Get flood risk for a specific address"""
    # Find closest gauge
    gauge, distance = find_closest_gauge(lat, lng)
    
    if not gauge:
        return {"error": "No flood gauge found near this location"}
    
    # Calculate risk
    tier, score, buffer, current, flood, distance = calculate_risk_from_gauge(gauge, distance)
    
    # Handle case where risk calculation failed
    if tier == "UNKNOWN":
        return {"error": "Could not calculate risk for this location"}
    
    # Multilingual messages
    messages = {
        "en": f"Flood risk at {address} is {tier}. The nearest gauge is {distance:.1f} miles away with water level at {current} ft (floods at {flood} ft).",
        "es": f"El riesgo de inundación en {address} es {tier}. El medidor más cercano está a {distance:.1f} millas con nivel de agua en {current} ft (inunda en {flood} ft).",
        "vi": f"Nguy cơ lũ lụt tại {address} là {tier}. Máy đo gần nhất cách {distance:.1f} dặm với mực nước ở {current} ft (ngập ở {flood} ft)."
    }
    
    return {
        "address": address,
        "risk_tier": tier,
        "risk_score": score,
        "buffer_ft": round(buffer, 1),
        "nearest_gauge_distance_miles": round(distance, 2),
        "message": messages["en"]
    }

@app.get("/gauges")
def get_all_gauges():
    """Get all 39 flood gauges with locations and risk levels"""
    # Updated working URL (same as find_closest_gauge)
    url = "https://www.harriscountyfws.org/Home/GetSiteRecentData?regionId=3&regionId=24&regionId=25&regionId=26&regionId=21&regionId=4&regionId=10&regionId=22&regionId=1&regionId=14&regionId=18&regionId=19&regionId=23&regionId=20&timeSpan=7&dt=1779069600000"
    headers = {"Referer": "https://www.harriscountyfws.org/"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise error if status is not 200
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch data from HCFWS: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
    
    result = []
    
    for site in data.get("features", []):
        try:
            props = site.get("properties", {})
            
            # Safe coordinate extraction with validation
            geometry = site.get("geometry", {})
            coordinates = geometry.get("coordinates", [0, 0])
            
            # Skip if no coordinates
            if len(coordinates) < 2:
                continue
            
            # Safely convert coordinates to float
            try:
                longitude = float(coordinates[0])
                latitude = float(coordinates[1])
            except (ValueError, TypeError):
                continue  # Skip this gauge if coordinates are invalid
            
            # Get stream data safely
            stream_data = props.get("StreamData", [])
            if not stream_data:
                continue
                
            stream = stream_data[0]
            current = stream.get("CurrentLevel", 0)
            
            channel_info = stream.get("ChannelInfo", {})
            flood = channel_info.get("FloodLevelIndicator")
            
            # Skip if no flood level set
            if flood is None or flood == 999:
                continue
            
            buffer = flood - current
            
            # Calculate risk tier
            if buffer <= 0:
                risk = "CRITICAL"
            elif buffer <= 2:
                risk = "HIGH"
            elif buffer <= 5:
                risk = "MEDIUM"
            elif buffer <= 10:
                risk = "LOW"
            else:
                risk = "SAFE"
            
            result.append({
                "id": props.get("SiteId"),
                "latitude": latitude,
                "longitude": longitude,
                "current_level_ft": current,
                "flood_level_ft": flood,
                "buffer_ft": round(buffer, 1),
                "risk_tier": risk
            })
        except Exception:
            # Skip this gauge if any error occurs
            continue
    
    return {"count": len(result), "gauges": result}

@app.get("/")
def root():
    """Root endpoint for health checks"""
    return {
        "message": "BayouGuard API is running!",
        "endpoints": {
            "/risk": "GET - Get flood risk for an address (requires lat, lng, address)",
            "/gauges": "GET - Get all flood gauges with risk levels",
            "/docs": "GET - Interactive API documentation"
        }
    }