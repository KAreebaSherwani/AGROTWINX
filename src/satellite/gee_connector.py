import ee
import os
import json
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from config import GEE_PROJECT_ID, PAKISTAN_CITIES

class GEEConnector:
    """Google Earth Engine connector for satellite data"""
    
    def __init__(self):
        try:
            # Prefer service-account auth (works locally AND when deployed).
            # Falls back to browser/CLI auth if no service account is set.
            key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if key_path and os.path.exists(key_path):
                sa_email = json.load(open(key_path)).get("client_email")
                credentials = ee.ServiceAccountCredentials(sa_email, key_path)
                ee.Initialize(credentials, project=GEE_PROJECT_ID)
                print("✅ Google Earth Engine initialized (service account)")
            else:
                ee.Initialize(project=GEE_PROJECT_ID)
                print("✅ Google Earth Engine initialized (browser auth)")
        except Exception as e:
            print(f"❌ GEE initialization failed: {e}")
            print("Run: earthengine authenticate  (local)  OR set GOOGLE_APPLICATION_CREDENTIALS")
            raise
    
    def get_sentinel2_image(self, lat, lon, start_date, end_date, buffer_km=2):
        """
        Get Sentinel-2 image for a location
        
        Args:
            lat, lon: Coordinates
            start_date, end_date: Date range (YYYY-MM-DD)
            buffer_km: Area around point in kilometers
        
        Returns:
            Dictionary with NDVI, NDWI, LAI values
        """
        # Create point and buffer
        point = ee.Geometry.Point([lon, lat])
        region = point.buffer(buffer_km * 1000)  # Convert km to meters
        
        # Get Sentinel-2 collection
        collection = (ee.ImageCollection('COPERNICUS/S2_SR')
                     .filterBounds(region)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                     .sort('CLOUDY_PIXEL_PERCENTAGE'))
        
        # Get the least cloudy image
        if collection.size().getInfo() == 0:
            print(f"⚠️  No images found for {lat}, {lon} between {start_date} and {end_date}")
            return None
        
        image = collection.first()
        
        # Calculate indices
        ndvi = self.calculate_ndvi(image)
        ndwi = self.calculate_ndwi(image)
        lai = self.calculate_lai(ndvi)
        
        # Get cloud cover
        cloud_cover = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        
        # Get values for the region
        stats = (ee.Image.cat([ndvi, ndwi, lai])
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=region,
                    scale=10,
                    maxPixels=1e9
                ))
        
        result = stats.getInfo()
        
        return {
            'date': image.date().format('YYYY-MM-dd').getInfo(),
            'ndvi': result.get('NDVI'),
            'ndwi': result.get('NDWI'),
            'lai': result.get('LAI'),
            'cloud_cover': cloud_cover
        }
    
    def calculate_ndvi(self, image):
        """Calculate NDVI from Sentinel-2 image"""
        nir = image.select('B8')   # Near-Infrared
        red = image.select('B4')   # Red
        
        ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI')
        return ndvi
    
    def calculate_ndwi(self, image):
        """Calculate NDWI (water content)"""
        nir = image.select('B8')
        swir = image.select('B11')  # Short-Wave Infrared
        
        ndwi = nir.subtract(swir).divide(nir.add(swir)).rename('NDWI')
        return ndwi
    
    def calculate_lai(self, ndvi):
        """Estimate LAI (Leaf Area Index) from NDVI"""
        # Simplified formula: LAI ≈ 3.618 * NDVI - 0.118
        lai = ndvi.multiply(3.618).subtract(0.118).rename('LAI')
        return lai
    
    def get_timeseries(self, lat, lon, start_date, end_date, interval_days=5):
        """
        Get time series of satellite observations
        
        Returns list of observations
        """
        observations = []
        
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current_date <= end:
            # Define 5-day window
            window_start = current_date.strftime('%Y-%m-%d')
            window_end = (current_date + timedelta(days=interval_days)).strftime('%Y-%m-%d')
            
            # Get image
            obs = self.get_sentinel2_image(lat, lon, window_start, window_end)
            
            if obs:
                observations.append(obs)
                print(f"✅ {obs['date']}: NDVI={obs['ndvi']:.3f}, NDWI={obs['ndwi']:.3f}")
            
            current_date += timedelta(days=interval_days)
        
        return observations

    def get_tile_url(self, lat, lon, start_date, end_date, index="NDVI", buffer_km=15):
        """
        Generate a live GEE map tile URL for NDVI or NDWI over a region.
        Returns {tile_url, date, cloud_cover, center} or None.
        Reuses calculate_ndvi / calculate_ndwi.
        """
        import config

        point = ee.Geometry.Point([lon, lat])
        region = point.buffer(buffer_km * 1000)

        collection = (ee.ImageCollection('COPERNICUS/S2_SR')
                      .filterBounds(region)
                      .filterDate(start_date, end_date)
                      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',
                                           config.CLOUD_COVER_THRESHOLD))
                      .sort('CLOUDY_PIXEL_PERCENTAGE'))

        if collection.size().getInfo() == 0:
            return None

        image = collection.first()

        if index.upper() == "NDWI":
            layer = self.calculate_ndwi(image).clip(region)
            vis = {"min": -0.3, "max": 0.5,
                   "palette": ["#8c510a", "#d8b365", "#f6e8c3",
                               "#c7eae5", "#5ab4ac", "#01665e"]}
        else:  # NDVI
            layer = self.calculate_ndvi(image).clip(region)
            vis = {"min": config.VIS_PARAMS["min"],
                   "max": config.VIS_PARAMS["max"],
                   "palette": config.VIS_PARAMS["palette"]}

        # getMapId returns a tile URL template Leaflet can use
        map_id = layer.getMapId(vis)
        tile_url = map_id["tile_fetcher"].url_format

        cloud_cover = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        date = image.date().format('YYYY-MM-dd').getInfo()

        return {
            "tile_url": tile_url,
            "index": index.upper(),
            "date": date,
            "cloud_cover": cloud_cover,
            "center": {"lat": lat, "lon": lon},
        }

# Test the connector
if __name__ == "__main__":
    connector = GEEConnector()
    
    # Test with Sheikhupura (rice area)
    city = 'Sheikhupura'
    coords = PAKISTAN_CITIES[city]
    
    print(f"\nTesting {city}...")
    print(f"Coordinates: {coords['lat']}, {coords['lon']}")
    
    # Get last 3 months
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    print(f"Date range: {start_date} to {end_date}\n")
    
    observations = connector.get_timeseries(
        coords['lat'],
        coords['lon'],
        start_date,
        end_date,
        interval_days=10
    )
    
    print(f"\n✅ Retrieved {len(observations)} observations")