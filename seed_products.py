# seed_products.py
"""
AgroTwinX — Product Catalog seeder (Supabase / PostgreSQL)
==========================================================
Creates a `products` table and seeds it with REAL Pakistani agri-input
products (seeds, fertilizers, pesticides/fungicides) from real brands
(FFC/Sona, Engro, Fatima/Sarsabz, Bayer, Syngenta, FMC), with bilingual
fields and a target_disease link so Page 5 (B2B hub) can auto-suggest
treatments after the Page 3 disease diagnosis.

Disease names in `target_disease` EXACTLY match config.COMMON_DISEASES so the
frontend can filter products by the diagnosed disease string.

Prices are realistic mid-2026 Pakistani market figures (PKR). They are
indicative retail ranges from public price lists (Kissan Cares / IR Farm /
FFC & Engro rate lists, 2026) and should be treated as guide prices, not
live quotes. Pack sizes are noted in `unit`.

RUN (from project root, with DATABASE_URL in .env):
  python seed_products.py            # create table + insert (skips if already seeded)
  python seed_products.py --reset    # drop + recreate + reseed
"""

import os
import sys
import argparse
from pathlib import Path

# allow importing the project's Database class + config
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import psycopg2
import psycopg2.extras


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS products (
    product_id        SERIAL PRIMARY KEY,
    category          TEXT NOT NULL,          -- 'seed' | 'fertilizer' | 'pesticide'
    subcategory       TEXT,                   -- 'fungicide' | 'insecticide' | 'urea' | 'dap' | 'wheat_seed' | 'rice_seed' ...
    name              TEXT NOT NULL,          -- product/brand name (English)
    name_urdu         TEXT,                   -- product name (Urdu)
    brand             TEXT,                   -- manufacturer / company
    active_ingredient TEXT,                   -- chemistry (for pesticides/fungicides)
    crop              TEXT,                   -- 'rice' | 'wheat' | 'both'
    target_disease    TEXT,                   -- matches config.COMMON_DISEASES exactly (NULL for fertilizers/seeds)
    price_pkr         INTEGER,                -- indicative retail price (PKR)
    unit              TEXT,                   -- pack size, e.g. '50 kg bag', '200 ml', '1 L', '10 kg'
    application_en    TEXT,                   -- how/when to apply (English)
    application_ur    TEXT,                   -- how/when to apply (Urdu)
    is_organic        BOOLEAN DEFAULT FALSE,  -- organic/biological option flag
    active            BOOLEAN DEFAULT TRUE
);
"""

# ---------------------------------------------------------------------------
# Disease name constants — MUST match config.COMMON_DISEASES exactly.
# rice:  'Rice Blast','Bacterial Leaf Blight','Brown Spot','Tungro','Sheath Blight','False Smut'
# wheat: 'Yellow Rust (Stripe Rust)','Leaf Rust (Brown Rust)','Stem Rust (Black Rust)',
#        'Powdery Mildew','Septoria Leaf Blotch','Leaf Blight'
# ---------------------------------------------------------------------------

PRODUCTS = [
    # ============================= FUNGICIDES (pesticide / fungicide) =============================
    # Propiconazole — broad triazole, the workhorse for wheat rusts + rice blast/leaf spots
    dict(category="pesticide", subcategory="fungicide",
         name="Tilt 250 EC", name_urdu="ٹِلٹ 250 EC", brand="Syngenta",
         active_ingredient="Propiconazole 25% EC", crop="wheat",
         target_disease="Yellow Rust (Stripe Rust)", price_pkr=2200, unit="250 ml",
         application_en="Spray at first rust pustules; 200 ml/acre in 100 L water. Repeat after 15 days if needed.",
         application_ur="زنگ کے ابتدائی دھبوں پر سپرے کریں؛ 200 ملی لیٹر فی ایکڑ 100 لیٹر پانی میں۔ ضرورت ہو تو 15 دن بعد دہرائیں۔"),
    dict(category="pesticide", subcategory="fungicide",
         name="Tilt 250 EC", name_urdu="ٹِلٹ 250 EC", brand="Syngenta",
         active_ingredient="Propiconazole 25% EC", crop="wheat",
         target_disease="Leaf Rust (Brown Rust)", price_pkr=2200, unit="250 ml",
         application_en="200 ml/acre in 100 L water at first sign of brown pustules.",
         application_ur="بھورے دھبوں کی پہلی علامت پر 200 ملی لیٹر فی ایکڑ 100 لیٹر پانی میں۔"),
    dict(category="pesticide", subcategory="fungicide",
         name="Tilt 250 EC", name_urdu="ٹِلٹ 250 EC", brand="Syngenta",
         active_ingredient="Propiconazole 25% EC", crop="wheat",
         target_disease="Stem Rust (Black Rust)", price_pkr=2200, unit="250 ml",
         application_en="200 ml/acre; act fast — stem rust spreads quickly in warm humid weather.",
         application_ur="200 ملی لیٹر فی ایکڑ؛ جلدی کریں — تنے کا زنگ گرم مرطوب موسم میں تیزی سے پھیلتا ہے۔"),
    # Nativo (Tebuconazole + Trifloxystrobin) — Bayer, rusts + blast + sheath blight
    dict(category="pesticide", subcategory="fungicide",
         name="Nativo 75 WG", name_urdu="نیٹیوو 75 WG", brand="Bayer",
         active_ingredient="Tebuconazole 50% + Trifloxystrobin 25% WG", crop="both",
         target_disease="Yellow Rust (Stripe Rust)", price_pkr=1850, unit="100 g",
         application_en="40 g/acre in 100 L water. Strong protective + curative action on rusts.",
         application_ur="40 گرام فی ایکڑ 100 لیٹر پانی میں۔ زنگ پر مضبوط حفاظتی و علاجی اثر۔"),
    dict(category="pesticide", subcategory="fungicide",
         name="Nativo 75 WG", name_urdu="نیٹیوو 75 WG", brand="Bayer",
         active_ingredient="Tebuconazole 50% + Trifloxystrobin 25% WG", crop="rice",
         target_disease="Rice Blast", price_pkr=1850, unit="100 g",
         application_en="40 g/acre at early lesion stage; repeat at booting if pressure is high.",
         application_ur="40 گرام فی ایکڑ ابتدائی دھبوں پر؛ شدت زیادہ ہو تو گابھے کے وقت دہرائیں۔"),
    dict(category="pesticide", subcategory="fungicide",
         name="Nativo 75 WG", name_urdu="نیٹیوو 75 WG", brand="Bayer",
         active_ingredient="Tebuconazole 50% + Trifloxystrobin 25% WG", crop="rice",
         target_disease="Sheath Blight", price_pkr=1850, unit="100 g",
         application_en="40 g/acre directed at the sheath/lower canopy at tillering–booting.",
         application_ur="40 گرام فی ایکڑ، کھیلوں اور نچلے حصے پر، پھٹاؤ سے گابھے کے دوران۔"),
    # Amistar Top (Azoxystrobin + Difenoconazole) — Syngenta, blast/brown spot/sheath
    dict(category="pesticide", subcategory="fungicide",
         name="Amistar Top 325 SC", name_urdu="ایمسٹار ٹاپ 325 SC", brand="Syngenta",
         active_ingredient="Azoxystrobin 200 + Difenoconazole 125 SC", crop="rice",
         target_disease="Brown Spot", price_pkr=2600, unit="200 ml",
         application_en="100–120 ml/acre in 100 L water; preventive + curative on leaf spots.",
         application_ur="100–120 ملی لیٹر فی ایکڑ 100 لیٹر پانی میں؛ پتوں کے دھبوں پر حفاظتی و علاجی۔"),
    dict(category="pesticide", subcategory="fungicide",
         name="Amistar Top 325 SC", name_urdu="ایمسٹار ٹاپ 325 SC", brand="Syngenta",
         active_ingredient="Azoxystrobin 200 + Difenoconazole 125 SC", crop="rice",
         target_disease="False Smut", price_pkr=2600, unit="200 ml",
         application_en="Apply at booting (before heading) as a preventive spray; 100 ml/acre.",
         application_ur="گابھے کے وقت (سٹہ نکلنے سے پہلے) حفاظتی سپرے؛ 100 ملی لیٹر فی ایکڑ۔"),
    # Topsin-M (Thiophanate-methyl) — broad, leaf blight / blotch
    dict(category="pesticide", subcategory="fungicide",
         name="Topsin-M 70 WP", name_urdu="ٹاپسن-ایم 70 WP", brand="FMC",
         active_ingredient="Thiophanate-methyl 70% WP", crop="wheat",
         target_disease="Septoria Leaf Blotch", price_pkr=1500, unit="500 g",
         application_en="250–300 g/acre in 100 L water at first blotch symptoms.",
         application_ur="بلاچ کی پہلی علامت پر 250–300 گرام فی ایکڑ 100 لیٹر پانی میں۔"),
    dict(category="pesticide", subcategory="fungicide",
         name="Topsin-M 70 WP", name_urdu="ٹاپسن-ایم 70 WP", brand="FMC",
         active_ingredient="Thiophanate-methyl 70% WP", crop="wheat",
         target_disease="Leaf Blight", price_pkr=1500, unit="500 g",
         application_en="250 g/acre; repeat after 12–15 days under wet conditions.",
         application_ur="250 گرام فی ایکڑ؛ نمی والے حالات میں 12–15 دن بعد دہرائیں۔"),
    # Cabrio Top / Sulphur — powdery mildew
    dict(category="pesticide", subcategory="fungicide",
         name="Kumulus DF (Sulphur)", name_urdu="کمولس DF (سلفر)", brand="Bayer",
         active_ingredient="Sulphur 80% WG", crop="wheat",
         target_disease="Powdery Mildew", price_pkr=900, unit="1 kg",
         application_en="500 g–1 kg/acre at first white powder; avoid spraying in extreme heat.",
         application_ur="سفید سفوف کی پہلی علامت پر 500 گرام–1 کلو فی ایکڑ؛ شدید گرمی میں سپرے سے گریز کریں۔"),
    # Copper oxychloride — bacterial leaf blight (rice)
    dict(category="pesticide", subcategory="bactericide",
         name="Copper Oxychloride 50 WP", name_urdu="کاپر آکسی کلورائیڈ 50 WP", brand="Sygenta/Generic",
         active_ingredient="Copper Oxychloride 50% WP", crop="rice",
         target_disease="Bacterial Leaf Blight", price_pkr=1100, unit="500 g",
         application_en="Copper-based spray to limit bacterial spread; 250–300 g/acre. Drain excess field water.",
         application_ur="بیکٹیریا کے پھیلاؤ کو روکنے کے لیے کاپر سپرے؛ 250–300 گرام فی ایکڑ۔ کھیت سے زائد پانی نکال دیں۔"),

    # ---- Organic / biological options (paired with the chemical ones) ----
    dict(category="pesticide", subcategory="biopesticide",
         name="Neem Oil Biopesticide", name_urdu="نیم آئل بایو پیسٹیسائیڈ", brand="Welcare Agro",
         active_ingredient="Azadirachtin (neem extract)", crop="both",
         target_disease="Brown Spot", price_pkr=750, unit="1 L", is_organic=True,
         application_en="Organic option: 3–5 ml/L water, spray in evening. Mild, preventive; use early.",
         application_ur="نامیاتی آپشن: 3–5 ملی لیٹر فی لیٹر پانی، شام کو سپرے کریں۔ ہلکا، حفاظتی؛ ابتدا میں استعمال کریں۔"),
    dict(category="pesticide", subcategory="biopesticide",
         name="Trichoderma Bio-Fungicide", name_urdu="ٹرائیکوڈرما بایو فنجی سائیڈ", brand="Greenlet Intl.",
         active_ingredient="Trichoderma harzianum", crop="both",
         target_disease="Sheath Blight", price_pkr=850, unit="1 kg", is_organic=True,
         application_en="Organic option: soil/seed application to suppress soil-borne fungi. Use preventively.",
         application_ur="نامیاتی آپشن: مٹی/بیج پر استعمال تاکہ زمینی فنگس کو دبایا جا سکے۔ بچاؤ کے طور پر استعمال کریں۔"),

    # ============================= FERTILIZERS =============================
    dict(category="fertilizer", subcategory="urea",
         name="Sona Urea (Prilled)", name_urdu="سونا یوریا", brand="FFC",
         active_ingredient="Nitrogen 46%", crop="both", target_disease=None,
         price_pkr=4450, unit="50 kg bag",
         application_en="Top-dressing N source. Wheat: ~2 bags/acre split at tillering & jointing. Rice: split doses.",
         application_ur="نائٹروجن کا ذریعہ۔ گندم: ~2 بوری فی ایکڑ، پھٹاؤ اور جوڑ بننے پر تقسیم۔ چاول: تقسیم شدہ مقدار۔"),
    dict(category="fertilizer", subcategory="urea",
         name="Engro Urea", name_urdu="اینگرو یوریا", brand="Engro",
         active_ingredient="Nitrogen 46%", crop="both", target_disease=None,
         price_pkr=4435, unit="50 kg bag",
         application_en="Nitrogen top-dressing; apply in 2–3 splits during vegetative growth.",
         application_ur="نائٹروجن ٹاپ ڈریسنگ؛ نشوونما کے دوران 2–3 اقساط میں ڈالیں۔"),
    dict(category="fertilizer", subcategory="dap",
         name="Sona DAP", name_urdu="سونا ڈی اے پی", brand="FFC",
         active_ingredient="Nitrogen 18% + Phosphorus 46%", crop="both", target_disease=None,
         price_pkr=14850, unit="50 kg bag",
         application_en="Basal fertilizer at sowing. Standard: 1 bag/acre for wheat at planting.",
         application_ur="بوائی کے وقت بنیادی کھاد۔ معیاری: گندم کے لیے 1 بوری فی ایکڑ بوائی پر۔"),
    dict(category="fertilizer", subcategory="dap",
         name="Sarsabz DAP", name_urdu="سرسبز ڈی اے پی", brand="Fatima Fertilizer",
         active_ingredient="Nitrogen 18% + Phosphorus 46%", crop="both", target_disease=None,
         price_pkr=14650, unit="50 kg bag",
         application_en="Basal phosphorus source at sowing; economical alternative to Sona/Engro DAP.",
         application_ur="بوائی پر فاسفورس کا بنیادی ذریعہ؛ سونا/اینگرو کا کفایتی متبادل۔"),
    dict(category="fertilizer", subcategory="sop",
         name="Sona SOP (Potash)", name_urdu="سونا ایس او پی (پوٹاش)", brand="FFC",
         active_ingredient="Potassium 50% (Sulphate of Potash)", crop="both", target_disease=None,
         price_pkr=13638, unit="50 kg bag",
         application_en="Potassium for grain filling & disease resistance; apply at land prep.",
         application_ur="دانہ بھرنے اور بیماری کے خلاف مزاحمت کے لیے پوٹاشیم؛ زمین کی تیاری پر ڈالیں۔"),
    dict(category="fertilizer", subcategory="micronutrient",
         name="Sona Zinc Granular", name_urdu="سونا زنک گرینولر", brand="FFC",
         active_ingredient="Zinc 33%", crop="rice", target_disease=None,
         price_pkr=2650, unit="3 kg",
         application_en="Corrects zinc deficiency in rice (common in Punjab paddies); apply at transplanting.",
         application_ur="چاول میں زنک کی کمی دور کرتا ہے (پنجاب کی پنیری میں عام)؛ روپائی پر ڈالیں۔"),

    # ============================= SEEDS =============================
    dict(category="seed", subcategory="wheat_seed",
         name="Akbar-2019 Wheat Seed", name_urdu="اکبر-2019 گندم بیج", brand="Punjab Seed Corp.",
         active_ingredient=None, crop="wheat", target_disease=None,
         price_pkr=3200, unit="40 kg bag",
         application_en="High-yielding, rust-resistant wheat variety for Punjab; ~50 kg seed/acre.",
         application_ur="پنجاب کے لیے زیادہ پیداوار، زنگ مزاحم گندم قسم؛ ~50 کلو بیج فی ایکڑ۔"),
    dict(category="seed", subcategory="wheat_seed",
         name="Dilkash-2020 Wheat Seed", name_urdu="دلکش-2020 گندم بیج", brand="Punjab Seed Corp.",
         active_ingredient=None, crop="wheat", target_disease=None,
         price_pkr=3300, unit="40 kg bag",
         application_en="Yellow-rust tolerant variety; certified seed improves germination & uniformity.",
         application_ur="پیلے زنگ کے خلاف برداشت رکھنے والی قسم؛ تصدیق شدہ بیج اگاؤ اور یکسانیت بہتر کرتا ہے۔"),
    dict(category="seed", subcategory="rice_seed",
         name="Super Basmati Rice Seed", name_urdu="سپر باسمتی چاول بیج", brand="Guard Agri",
         active_ingredient=None, crop="rice", target_disease=None,
         price_pkr=4500, unit="10 kg",
         application_en="Premium aromatic basmati for central Punjab; ~8–10 kg seed/acre for nursery.",
         active=True),
    dict(category="seed", subcategory="rice_seed",
         name="Kainat / KSK-133 Rice Seed", name_urdu="کائنات / KSK-133 چاول بیج", brand="GreenGold Agri Seeds",
         active_ingredient=None, crop="rice", target_disease=None,
         price_pkr=4200, unit="10 kg",
         application_en="High-yielding coarse rice variety; good blast tolerance for Punjab paddies.",
         application_ur="زیادہ پیداوار والی موٹی چاول قسم؛ پنجاب کی پنیری کے لیے بلاسٹ برداشت میں اچھی۔"),
]


def connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL not set. Put your Supabase URI in .env first.")
        sys.exit(1)
    dsn = url.replace("+asyncpg", "").replace("+psycopg2", "")
    return psycopg2.connect(dsn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and recreate the products table")
    args = ap.parse_args()

    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    if args.reset:
        cur.execute("DROP TABLE IF EXISTS products;")
        print("🗑️  Dropped existing products table.")

    cur.execute(CREATE_SQL)
    print("✅ products table ready.")

    # Skip if already seeded (unless reset)
    cur.execute("SELECT COUNT(*) FROM products;")
    count = cur.fetchone()[0]
    if count > 0 and not args.reset:
        print(f"ℹ️  products already has {count} rows; not re-seeding. Use --reset to rebuild.")
        conn.commit()
        cur.close(); conn.close()
        return

    cols = ["category", "subcategory", "name", "name_urdu", "brand",
            "active_ingredient", "crop", "target_disease", "price_pkr", "unit",
            "application_en", "application_ur", "is_organic", "active"]
    inserted = 0
    for p in PRODUCTS:
        row = [p.get(c) for c in cols]
        placeholders = ", ".join(["%s"] * len(cols))
        cur.execute(
            f"INSERT INTO products ({', '.join(cols)}) VALUES ({placeholders})",
            row,
        )
        inserted += 1

    conn.commit()
    print(f"✅ Inserted {inserted} products.")

    # Show a quick summary
    cur.execute("SELECT category, COUNT(*) FROM products GROUP BY category ORDER BY category;")
    print("\n📦 Catalog summary:")
    for cat, n in cur.fetchall():
        print(f"   {cat:12s} : {n}")

    cur.close()
    conn.close()
    print("\nDone. Page 5 can now query products by target_disease to suggest treatments.")


if __name__ == "__main__":
    main()