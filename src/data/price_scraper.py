# src/data/price_scraper.py

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import MANDI_CITIES

class PriceScraper:
    """
    Scrape mandi prices from Pakistani agricultural websites
    """
    
    def __init__(self, db=None):
        self.db = db
        self.price_dir = Path('data/raw/prices')
        self.price_dir.mkdir(parents=True, exist_ok=True)
    
    def scrape_manual_entry(self):
        """
        Manual price entry system
        Since scraping can break, provide manual entry fallback
        """
        print("\n💰 Manual Price Entry")
        print("="*70)
        
        prices = []
        
        for city in MANDI_CITIES[:5]:  # Top 5 cities
            print(f"\n📍 {city}")
            
            try:
                rice_price = float(input(f"  Rice price (Rs/40kg): "))
                wheat_price = float(input(f"  Wheat price (Rs/40kg): "))
                
                prices.append({
                    'city': city,
                    'crop': 'rice',
                    'price_per_40kg': rice_price,
                    'date': datetime.now().date().isoformat(),
                    'source': 'manual_entry'
                })
                
                prices.append({
                    'city': city,
                    'crop': 'wheat',
                    'price_per_40kg': wheat_price,
                    'date': datetime.now().date().isoformat(),
                    'source': 'manual_entry'
                })
                
            except ValueError:
                print("  ⚠️  Invalid input, skipping...")
                continue
        
        # Save to database
        if self.db and prices:
            for price in prices:
                self.db.insert('market_prices', price)
            
            print(f"\n✅ {len(prices)} prices saved to database")
        
        # Save to CSV
        df = pd.DataFrame(prices)
        csv_file = self.price_dir / f'prices_{datetime.now().strftime("%Y%m%d")}.csv'
        df.to_csv(csv_file, index=False)
        print(f"✅ Saved to: {csv_file}")
        
        return prices
    
    def load_historical_data(self):
        """
        Load or create historical price data for training
        """
        print("\n📊 Loading historical price data...")
        
        historical_file = self.price_dir / 'historical_prices.csv'
        
        if historical_file.exists():
            df = pd.read_csv(historical_file)
            print(f"✅ Loaded {len(df)} historical records")
            return df
        
        # Create synthetic historical data for demo
        print("📝 Creating synthetic historical data...")
        
        dates = pd.date_range(
            start='2023-01-01',
            end=datetime.now(),
            freq='D'
        )
        
        data = []
        
        for city in MANDI_CITIES[:5]:
            # Base prices with seasonal variation
            rice_base = 3000 + (hash(city) % 500)
            wheat_base = 2200 + (hash(city) % 300)
            
            for date in dates:
                # Seasonal trend
                month = date.month
                
                # Rice prices peak during harvest (Oct-Nov)
                if month in [10, 11]:
                    rice_multiplier = 0.9  # Price drops during harvest
                elif month in [3, 4, 5]:
                    rice_multiplier = 1.15  # Price increases off-season
                else:
                    rice_multiplier = 1.0
                
                # Wheat prices peak during harvest (Apr-May)
                if month in [4, 5]:
                    wheat_multiplier = 0.9
                elif month in [9, 10, 11]:
                    wheat_multiplier = 1.12
                else:
                    wheat_multiplier = 1.0
                
                # Add random noise
                import random
                rice_noise = random.uniform(-100, 100)
                wheat_noise = random.uniform(-80, 80)
                
                rice_price = rice_base * rice_multiplier + rice_noise
                wheat_price = wheat_base * wheat_multiplier + wheat_noise
                
                data.append({
                    'city': city,
                    'crop': 'rice',
                    'price_per_40kg': round(rice_price, 0),
                    'date': date.strftime('%Y-%m-%d'),
                    'source': 'synthetic'
                })
                
                data.append({
                    'city': city,
                    'crop': 'wheat',
                    'price_per_40kg': round(wheat_price, 0),
                    'date': date.strftime('%Y-%m-%d'),
                    'source': 'synthetic'
                })
        
        df = pd.DataFrame(data)
        df.to_csv(historical_file, index=False)
        
        print(f"✅ Created {len(df)} synthetic records")
        print(f"📁 Saved to: {historical_file}")
        
        return df
    
    def get_latest_prices(self, city=None, crop=None):
        """Get latest prices from database"""
        if not self.db:
            return []
        
        query = "SELECT * FROM market_prices WHERE 1=1"
        params = []
        
        if city:
            query += " AND city = ?"
            params.append(city)
        
        if crop:
            query += " AND crop_type = ?"
            params.append(crop)
        
        query += " ORDER BY date DESC LIMIT 20"
        
        return self.db.query(query, params if params else None)

# Run scraper
if __name__ == "__main__":
    from utils.database import Database
    
    print("="*70)
    print("MANDI PRICE SCRAPER")
    print("="*70)
    
    db = Database()
    scraper = PriceScraper(db)
    
    print("\nOptions:")
    print("  1. Manual entry (enter prices manually)")
    print("  2. Load historical data (for training)")
    
    choice = input("\nChoose option (1 or 2): ").strip()
    
    if choice == '1':
        scraper.scrape_manual_entry()
    elif choice == '2':
        scraper.load_historical_data()
    else:
        print("Invalid choice")