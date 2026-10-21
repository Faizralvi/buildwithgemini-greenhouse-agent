# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

try:
    from a2ui.basic_catalog.provider import BasicCatalog
    from a2ui.schema.manager import A2uiSchemaManager
except ImportError:
    try:
        from .a2ui_utils import A2uiSchemaManager, BasicCatalog
    except ImportError:
        from a2ui_utils import A2uiSchemaManager, BasicCatalog
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

try:
    from .a2ui_utils import a2ui_callback
except ImportError:
    from a2ui_utils import a2ui_callback


MODEL = "gemini-3.8-flash"
PROJECT_ID = "qwiklabs-gcp-04-63b2ade03132"
BUCKET_NAME = "greenhouse-plants-qwiklabs-gcp-04-63b2ade03132"
COLLECTION_NAME = "plants"


def get_db() -> firestore.Client:
    """Returns a Firestore client initialized with the hardcoded project ID."""
    return firestore.Client(project=PROJECT_ID)


def list_plants(
    care_level: Optional[str] = None,
    max_price: Optional[float] = None,
) -> list[dict[str, Any]]:
    """List and search plants available in the greenhouse inventory.

    Args:
        care_level: Optional filter by care difficulty ("Easy", "Moderate", "Expert").
        max_price: Optional maximum price filter.

    Returns:
        A list of plant dictionaries containing plant details, pricing, and stock.
    """
    db = get_db()
    docs = db.collection(COLLECTION_NAME).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue
        data["id"] = doc.id
        if care_level and data.get("care_level", "").lower() != care_level.lower():
            continue
        if max_price is not None and data.get("price", 0) > max_price:
            continue
        results.append(data)
    return results


def get_plant_details(plant_name: str) -> dict[str, Any]:
    """Retrieve detailed information and care instructions for a specific plant.

    Args:
        plant_name: Name or ID of the plant (e.g., 'Monstera Deliciosa', 'snake-plant').

    Returns:
        Dictionary with full plant details, or an error message if not found.
    """
    db = get_db()
    clean_name = plant_name.strip().lower().replace(" ", "-")
    doc_ref = db.collection(COLLECTION_NAME).document(clean_name)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    # Fallback search by matching 'name' field
    docs = db.collection(COLLECTION_NAME).stream()
    for d in docs:
        data = d.to_dict()
        if data and data.get("name", "").lower() == plant_name.strip().lower():
            data["id"] = d.id
            return data

    return {"error": f"Plant '{plant_name}' not found in inventory."}


def add_plant(
    name: str,
    species: str,
    care_level: str,
    light: str,
    watering: str,
    price: float,
    stock: int,
    description: str,
) -> dict[str, Any]:
    """Add a new plant to the greenhouse inventory.

    Args:
        name: Common name of the plant (e.g., 'Pilea Peperomioides').
        species: Botanical/scientific species name (e.g., 'Pilea peperomioides').
        care_level: Care level rating ('Easy', 'Moderate', 'Expert').
        light: Lighting requirements (e.g., 'Bright indirect light').
        watering: Watering instructions (e.g., 'Water when top 1 inch dry').
        price: Price in USD.
        stock: Quantity in stock.
        description: Brief description of the plant.

    Returns:
        Status message with the created plant record.
    """
    db = get_db()
    doc_id = name.strip().lower().replace(" ", "-")
    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
    plant_data = {
        "id": doc_id,
        "name": name.strip(),
        "species": species.strip(),
        "care_level": care_level.strip(),
        "light": light.strip(),
        "watering": watering.strip(),
        "price": float(price),
        "stock": int(stock),
        "description": description.strip(),
    }
    doc_ref.set(plant_data)
    return {"status": "success", "message": f"Added '{name}' to inventory.", "plant": plant_data}


def update_plant_stock(plant_name: str, new_stock: int) -> dict[str, Any]:
    """Update inventory stock quantity for an existing plant.

    Args:
        plant_name: Name or ID of the plant to update.
        new_stock: The updated quantity count in stock.

    Returns:
        Status message confirming the stock update.
    """
    db = get_db()
    clean_name = plant_name.strip().lower().replace(" ", "-")
    doc_ref = db.collection(COLLECTION_NAME).document(clean_name)
    doc = doc_ref.get()

    target_ref = None
    if doc.exists:
        target_ref = doc_ref
    else:
        # Search by matching name field
        for d in db.collection(COLLECTION_NAME).stream():
            data = d.to_dict()
            if data and data.get("name", "").lower() == plant_name.strip().lower():
                target_ref = db.collection(COLLECTION_NAME).document(d.id)
                break

    if not target_ref:
        return {"error": f"Plant '{plant_name}' not found. Cannot update stock."}

    target_ref.update({"stock": int(new_stock)})
    return {"status": "success", "message": f"Updated stock for '{plant_name}' to {new_stock}."}


def calculate_watering_schedule(
    pot_size_inches: float,
    humidity_percent: float,
    temperature_f: float,
    season: str = "summer",
) -> dict[str, Any]:
    """Calculate customized watering interval and volume for a plant based on room environment.

    Args:
        pot_size_inches: Diameter of the plant pot in inches (e.g., 6.0).
        humidity_percent: Relative room humidity percentage (e.g., 45.0).
        temperature_f: Room temperature in Fahrenheit (e.g., 72.0).
        season: Current season ('spring', 'summer', 'autumn', 'winter').

    Returns:
        Dictionary with recommended watering interval (days), water volume (mL), and advice.
    """
    base_days = 7.0 + (pot_size_inches * 0.5)

    if humidity_percent < 30:
        base_days -= 2.0
    elif humidity_percent > 60:
        base_days += 2.0

    if temperature_f > 75:
        base_days -= 1.5
    elif temperature_f < 65:
        base_days += 2.0

    if season.strip().lower() == "winter":
        base_days *= 1.5

    recommended_days = max(2, round(base_days))
    water_volume_ml = int(pot_size_inches * 75)

    return {
        "recommended_interval_days": recommended_days,
        "water_volume_ml": water_volume_ml,
        "environmental_summary": f"{pot_size_inches}\" pot at {temperature_f}°F with {humidity_percent}% humidity ({season.title()})",
        "tip": f"Water with approximately {water_volume_ml} mL every {recommended_days} days. Check top soil moisture before watering.",
    }


def get_local_growing_conditions(location: str) -> dict[str, Any]:
    """Fetch live real-time local weather, temperature, and humidity conditions for plant care.

    Args:
        location: City name or region (e.g., 'San Francisco', 'New York', 'London', 'Tokyo').

    Returns:
        Dictionary containing real-time temperature, humidity, weather condition, and plant care advice.
    """
    import urllib.parse
    import urllib.request
    import json

    try:
        encoded_loc = urllib.parse.quote(location.strip())
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_loc}&count=1&language=en&format=json"
        
        req = urllib.request.Request(geo_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode())
        
        results = geo_data.get("results")
        if not results:
            return {"error": f"Could not find coordinates for location: '{location}'"}
        
        place = results[0]
        lat = place["latitude"]
        lon = place["longitude"]
        city_name = place.get("name", location)
        country = place.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,precipitation"
        req_weather = urllib.request.Request(weather_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req_weather, timeout=5) as response:
            weather_data = json.loads(response.read().decode())
        
        current = weather_data.get("current", {})
        temp_c = current.get("temperature_2m", 0.0)
        temp_f = round((temp_c * 9/5) + 32, 1)
        humidity = current.get("relative_humidity_2m", 0)
        precipitation = current.get("precipitation", 0.0)

        advice = []
        if humidity < 35:
            advice.append("Low air humidity: Consider misting tropical foliage or using a pebble tray.")
        elif humidity > 70:
            advice.append("High humidity: Ideal for tropical plants; ensure good ventilation to avoid mold.")
        
        if temp_f < 50:
            advice.append("Chilly conditions: Keep sensitive plants away from cold drafts and uninsulated windows.")
        elif temp_f > 85:
            advice.append("Warm conditions: Soil evaporates quickly; check moisture levels more frequently.")

        return {
            "location": f"{city_name}, {country}".strip(", "),
            "temperature_f": temp_f,
            "temperature_c": temp_c,
            "relative_humidity_percent": humidity,
            "precipitation_mm": precipitation,
            "growing_advice": " ".join(advice) or "Standard indoor growing conditions.",
        }
    except Exception as e:
        return {"error": f"Failed to retrieve weather data for '{location}': {str(e)}"}


def geocode_address(address: str) -> dict[str, Any]:
    """Turn an address or location name into geographic coordinates using the Google Maps Geocoding API.

    Args:
        address: Street address, landmark, or city to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        Dictionary containing formatted address, latitude, and longitude.
    """
    import os
    import json
    import urllib.parse
    import urllib.request
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return {"error": "GOOGLE_MAPS_API_KEY is not configured in .env. Please provide a valid Google Maps API key."}

    try:
        encoded_addr = urllib.parse.quote(address.strip())
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_addr}&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return {"error": f"Geocoding failed with status: {data.get('status')}, {data.get('error_message', 'No results found')}"}

        result = data["results"][0]
        loc = result["geometry"]["location"]
        return {
            "formatted_address": result.get("formatted_address"),
            "latitude": loc["lat"],
            "longitude": loc["lng"],
            "place_id": result.get("place_id"),
        }
    except Exception as e:
        return {"error": f"Failed to geocode address: {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "florist",
    radius_meters: float = 5000.0,
) -> list[dict[str, Any]]:
    """Find nearby places of a given type using Google Places API (New) searchNearby.

    Args:
        latitude: Latitude of the center search location.
        longitude: Longitude of the center search location.
        place_type: Place type to search for (e.g., 'florist', 'park', 'store', 'garden_center').
        radius_meters: Search radius in meters (max 50000, default 5000).

    Returns:
        List of nearby places with name, formatted address, location coordinates, and place types.
    """
    import os
    import json
    import urllib.request
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return [{"error": "GOOGLE_MAPS_API_KEY is not configured in .env. Please provide a valid Google Maps API key."}]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types",
    }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": min(max(radius_meters, 100.0), 50000.0),
            }
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        places = data.get("places", [])
        if not places:
            return []

        results = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "")
            formatted_address = p.get("formattedAddress", "")
            loc = p.get("location", {})
            types_list = p.get("types", [])
            results.append({
                "name": display_name,
                "address": formatted_address,
                "location": {
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                },
                "types": types_list,
            })
        return results
    except Exception as e:
        return [{"error": f"Failed to search nearby places: {str(e)}"}]


async def generate_plant_image(
    prompt: str,
    plant_name: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Generate a visual image/photo for a plant or botanic arrangement using Gemini and upload to public cloud storage.

    Args:
        prompt: Detailed visual description for image generation (e.g., 'A lush, healthy Monstera Deliciosa in a terracotta pot with soft sunlight').
        plant_name: Optional common name of the plant to label the output.
        tool_context: ADK ToolContext automatically injected by the runtime.

    Returns:
        Dictionary containing image generation status, public Cloud Storage URL, and artifact filename.
    """
    from google import genai

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1"),
        ),
    )

    image_bytes = None
    mime_type = "image/jpeg"
    for part in response.parts or []:
        if part.inline_data and part.inline_data.data:
            image_bytes = part.inline_data.data
            mime_type = part.inline_data.mime_type or "image/jpeg"
            break

    if not image_bytes:
        return {"error": "Failed to generate image from prompt."}

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = (plant_name or "plant").lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    filename = f"{clean_name}_{timestamp}.jpg"

    # (1) Save artifact so it shows up in Playground's Artifacts panel
    if tool_context is not None:
        try:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)
        except Exception:
            pass

    # (2) Upload image bytes directly to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "image_url": public_url,
        "plant_name": plant_name or "plant",
        "filename": filename,
        "description": f"Generated image for {plant_name or prompt}",
    }


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each turn, send the session to Vertex AI Memory Bank for long-term extraction."""
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are the Greenhouse Assistant, an expert botanical and houseplant concierge. "
        "You remember the user's stated preferences, plant collections, growing experience, and past conversations "
        "across sessions to deliver personalized care. Always remember and strictly adhere to all user allergies, "
        "respiratory sensitivities, skin reactions, and pet toxicity constraints across sessions (e.g. avoiding high-pollen plants, "
        "toxic sap, or allergenic blooms). You assist users in finding suitable plants, looking up care "
        "requirements, checking inventory, fetching live local environmental conditions, locating local plant nurseries/florists, "
        "generating visual photos and portraits of plants, and managing the greenhouse plant database. "
        "Always use your tools to fetch accurate real-time details, manage inventory, and generate visual assets."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        list_plants,
        get_plant_details,
        add_plant,
        update_plant_stock,
        calculate_watering_schedule,
        get_local_growing_conditions,
        geocode_address,
        find_nearby_places,
        generate_plant_image,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
