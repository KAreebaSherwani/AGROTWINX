# seed_demo_data.py
"""
AgroTwinX — Demo Data Seeder
Runs the REAL pipeline end-to-end so every dashboard/WhatsApp page shows live numbers.

What it does (in order):
  1. Clears prior demo rows (keeps farmers/farms/digital_twins/buyers).
  2. Generates a season of satellite observations per twin (NDVI/NDWI/LAI) -> satellite_observations.
  3. Writes realistic yield + stubble predictions back into each digital_twin.
  4. Drives StubbleMarketplace.create_listing / find_buyers / create_transaction
     -> stubble_listings, stubble_transactions, platform_revenue, carbon_certificates (REAL 5% fee + carbon logic).
  5. Inserts disease detections, weather history, B2B clients + data reports.
  6. Aggregates a 30-day impact_metrics time series.

Run from project root:   python seed_demo_data.py
Safe to re-run (it clears demo tables first).
"""

import sys, os, json, random, math
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from src.utils.database import Database
from src.marketplace.stubble_marketplace import StubbleMarketplace

random.seed(42)  # reproducible demo

# Per-acre stubble yield (tons) and emission factors mirror config.py
STUBBLE_PER_ACRE = {"rice": 1.5, "wheat": 1.0}
YIELD_MAUNDS_PER_ACRE = {"rice": 42, "wheat": 36}

DISEASES = [
    ("بھورا دھبہ", "Brown Spot", "rice", "medium", "مینکوزیب سپرے کریں", "Apply Mancozeb fungicide"),
    ("بلاسٹ", "Rice Blast", "rice", "high", "ٹرائی سائیکلازول استعمال کریں", "Use Tricyclazole"),
    ("زنگ", "Leaf Rust", "wheat", "medium", "پروپیکونازول سپرے", "Spray Propiconazole"),
    ("کانگیاری", "Loose Smut", "wheat", "low", "بیج کو علاج شدہ استعمال کریں", "Use treated seed"),
]

def clear_demo_tables(db):
    tables = ["carbon_certificates","platform_revenue","stubble_transactions","stubble_listings",
              "satellite_observations","disease_detections","weather_data","data_reports",
              "b2b_clients","impact_metrics"]
    conn = db.get_connection(); cur = conn.cursor()
    for t in tables:
        try: cur.execute(f"DELETE FROM {t}")
        except Exception as e: print(f"  (skip {t}: {e})")
    conn.commit()
    print(f"🧹 Cleared {len(tables)} demo tables")

def seed_satellite_and_predictions(db):
    twins = db.query("""
        SELECT dt.twin_id, dt.farm_id, f.farmer_id, f.crop_type, f.area_acres,
               dt.current_state, dt.predictions
        FROM digital_twins dt JOIN farms f ON dt.farm_id = f.farm_id
    """)
    obs_count = 0
    for t in twins:
        crop = t["crop_type"]; area = float(t["area_acres"] or 4)
        # season of 6 observations, NDVI rising then dipping near maturity
        base = datetime.now() - timedelta(days=70)
        ndvi_curve = [0.32, 0.48, 0.63, 0.74, 0.71, 0.66]
        for i, nd in enumerate(ndvi_curve):
            d = (base + timedelta(days=i*12)).strftime("%Y-%m-%d")
            ndvi = round(nd + random.uniform(-0.03, 0.03), 3)
            db.insert("satellite_observations", {
                "twin_id": t["twin_id"], "observation_date": d,
                "ndvi": ndvi, "ndwi": round(0.30 + random.uniform(-0.05,0.05),3),
                "lai": round(ndvi*5.2,2), "cloud_cover": random.choice([5,10,12,18,8]),
            })
            obs_count += 1
        # realistic yield + stubble prediction
        yield_maunds = round(YIELD_MAUNDS_PER_ACRE[crop]*area*random.uniform(0.9,1.08),1)
        stubble = round(STUBBLE_PER_ACRE[crop]*area*random.uniform(0.92,1.08),2)
        cur_state = json.loads(t["current_state"]) if t["current_state"] else {}
        preds = json.loads(t["predictions"]) if t["predictions"] else {}
        cur_state["ndvi_current"] = ndvi_curve[-1]; cur_state["health_score"] = round(min(100, ndvi_curve[-1]*120),1)
        preds.update({
            "expected_yield_maunds": yield_maunds,
            "expected_yield_tons": round(yield_maunds*0.03732,2),
            "stubble_tons": stubble,
            "days_to_harvest": random.randint(3,9),
            "confidence": round(random.uniform(0.82,0.94),2),
        })
        db.update("digital_twins","farm_id",t["farm_id"],
                  {"current_state": json.dumps(cur_state), "predictions": json.dumps(preds)})
    print(f"🛰️  Inserted {obs_count} satellite observations + updated {len(twins)} twin predictions")
    return twins

def run_marketplace(db, twins):
    mkt = StubbleMarketplace(db)
    listings, txns = 0, 0
    for i, t in enumerate(twins):
        listing = mkt.create_listing(twin_id=t["farm_id"], farmer_id=t["farmer_id"])
        if not listing: continue
        listings += 1
        # ~70% of listings get sold (rest stay 'active' for realism)
        if i % 10 < 7:
            matches = mkt.find_buyers(listing["listing_id"])
            if matches:
                best = matches[0]
                tx = mkt.create_transaction(listing["listing_id"], best["buyer_id"])
                if tx: txns += 1
    print(f"💰 Created {listings} listings, {txns} completed transactions (revenue + carbon auto-recorded)")
    return listings, txns

def seed_diseases(db):
    farms = db.query("SELECT farm_id, crop_type FROM farms")
    n = 0
    for f in farms:
        if random.random() < 0.45:  # ~45% of farms had a detection
            opts = [d for d in DISEASES if d[2]==f["crop_type"]] or DISEASES
            dz = random.choice(opts)
            db.insert("disease_detections", {
                "farm_id": f["farm_id"],
                "detection_date": (datetime.now()-timedelta(days=random.randint(1,40))).strftime("%Y-%m-%d %H:%M:%S"),
                "image_path": f"data/uploads/leaf_{f['farm_id']}.jpg",
                "disease_name_urdu": dz[0], "disease_name_english": dz[1],
                "severity": dz[3], "confidence": round(random.uniform(0.86,0.97),2),
                "treatment_urdu": dz[4], "treatment_english": dz[5],
            }); n += 1
    print(f"🦠 Inserted {n} disease detections")

def seed_weather(db):
    locs = db.query("SELECT DISTINCT location_lat, location_lon FROM farmers WHERE location_lat IS NOT NULL LIMIT 4")
    n = 0
    for loc in locs:
        for day in range(30):
            d = (datetime.now()-timedelta(days=29-day)).strftime("%Y-%m-%d")
            tmax = round(random.uniform(28,38),1); tmin = round(tmax-random.uniform(8,12),1)
            db.insert("weather_data", {
                "location_lat": loc["location_lat"], "location_lon": loc["location_lon"], "date": d,
                "temp_max": tmax, "temp_min": tmin, "temp_avg": round((tmax+tmin)/2,1),
                "rainfall": round(random.choice([0,0,0,2,5,12])*random.random(),1),
                "humidity": random.randint(35,70), "wind_speed": round(random.uniform(4,18),1),
            }); n += 1
    print(f"🌦️  Inserted {n} weather rows")

def seed_b2b(db):
    clients = [
        ("Engro Fertilizers","fertilizer","Sales Lead","sales@engro.com","+924237xxxx","Pro",45000,"Punjab"),
        ("State Life Insurance","insurance","Crop Risk","crop@statelife.pk","+924299xxxx","Enterprise",80000,"Punjab,Sindh"),
        ("Guard Agri Seeds","seed","Procurement","info@guard.pk","+924235xxxx","Basic",20000,"Punjab"),
        ("Punjab Agri Dept","government","Policy Cell","data@agripunjab.gov.pk","+924299xxxx","Enterprise",0,"Punjab"),
    ]
    rep = 0
    for c in clients:
        cid = db.insert("b2b_clients", {
            "company_name":c[0],"client_type":c[1],"contact_person":c[2],"email":c[3],
            "phone_number":c[4],"subscription_plan":c[5],"monthly_fee":c[6],
            "region_coverage":c[7],"active":1,
            "start_date":(datetime.now()-timedelta(days=120)).strftime("%Y-%m-%d"),
            "end_date":(datetime.now()+timedelta(days=245)).strftime("%Y-%m-%d"),
        })
        for m in range(3):
            db.insert("data_reports", {
                "client_id":cid,"report_date":(datetime.now()-timedelta(days=30*m)).strftime("%Y-%m-%d"),
                "region":"Punjab","crop_type":random.choice(["rice","wheat"]),
                "report_data":json.dumps({"farms_covered":random.randint(50,400),"avg_ndvi":round(random.uniform(0.55,0.72),2)}),
                "delivered":1,
            }); rep += 1
    print(f"🏢 Inserted {len(clients)} B2B clients + {rep} data reports")

def seed_impact_timeseries(db):
    # Aggregate true totals from what we just created, spread over 30 days (cumulative)
    tx = db.query("SELECT quantity_tons, net_to_farmer, platform_fee FROM stubble_transactions")
    cc = db.query("SELECT co2_prevented_tons FROM carbon_certificates")
    b2b = db.query("SELECT COALESCE(SUM(monthly_fee),0) AS s FROM b2b_clients")[0]["s"] or 0
    tot_stub = sum(r["quantity_tons"] for r in tx)
    tot_earn = sum(r["net_to_farmer"] for r in tx)
    tot_fee  = sum(r["platform_fee"] for r in tx)
    tot_co2  = sum(r["co2_prevented_tons"] for r in cc)
    farmers = db.query("SELECT COUNT(*) c FROM farmers WHERE active = 1")[0]["c"]
    twins   = db.query("SELECT COUNT(*) c FROM digital_twins")[0]["c"]
    dz      = db.query("SELECT COUNT(*) c FROM disease_detections")[0]["c"]
    ntx     = len(tx)
    for day in range(30):
        frac = (day+1)/30.0
        db.insert("impact_metrics", {
            "metric_date": (datetime.now()-timedelta(days=29-day)).strftime("%Y-%m-%d"),
            "total_stubble_prevented_tons": round(tot_stub*frac,2),
            "total_co2_saved_tons": round(tot_co2*frac,2),
            "total_farmer_earnings": round(tot_earn*frac,0),
            "total_platform_revenue": round((tot_fee + b2b)*frac,0),
            "active_farmers": int(farmers*frac) or 1,
            "active_twins": int(twins*frac) or 1,
            "disease_detections_count": int(dz*frac),
            "transactions_count": int(ntx*frac),
        })
    print(f"📈 Impact: {tot_stub:.0f}t stubble, {tot_co2:.0f}t CO2 saved, "
          f"Rs {tot_earn:,.0f} to farmers, Rs {tot_fee+b2b:,.0f} platform revenue")

def main():
    print("="*70); print("AGROTWINX — DEMO DATA SEEDER"); print("="*70)
    db = Database()
    clear_demo_tables(db)
    twins = seed_satellite_and_predictions(db)
    run_marketplace(db, twins)
    seed_diseases(db)
    seed_weather(db)
    seed_b2b(db)
    seed_impact_timeseries(db)
    print("\n✅ Seed complete. Every dashboard page should now show real numbers.")

if __name__ == "__main__":
    main()