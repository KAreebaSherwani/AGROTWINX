# src/utils/db_models.py
"""
SQLAlchemy 2.0 ORM models for AgroTwinX (PostgreSQL + pgvector).
Mirrors the original 14 SQLite tables exactly (same names/columns) + adds
`agronomy_chunks` for RAG. Used to create the schema and by the async API.

EMBED_DIM is the single source of truth for the vector size — it MUST match
the embedding model's output_dimensionality (gemini-embedding-2 @ 1536).
"""

from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import (String, Integer, Float, Boolean, Date, DateTime, Text,
                        ForeignKey, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

EMBED_DIM = 1536  # gemini-embedding-2 output_dimensionality (<=2000 => HNSW-indexable)


class Base(DeclarativeBase):
    pass


class Farmer(Base):
    __tablename__ = "farmers"
    farmer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    location_lat: Mapped[float] = mapped_column(Float, nullable=False)
    location_lon: Mapped[float] = mapped_column(Float, nullable=False)
    district: Mapped[str | None] = mapped_column(Text)
    village: Mapped[str | None] = mapped_column(Text)
    registered_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    active: Mapped[int] = mapped_column(Integer, server_default="1")


class Farm(Base):
    __tablename__ = "farms"
    farm_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.farmer_id"), nullable=False)
    field_name: Mapped[str | None] = mapped_column(Text)
    crop_type: Mapped[str] = mapped_column(Text, nullable=False)
    area_acres: Mapped[float] = mapped_column(Float, nullable=False)
    soil_type: Mapped[str | None] = mapped_column(Text)
    planting_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_harvest_date: Mapped[date | None] = mapped_column(Date)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(Text, server_default="active")


class DigitalTwinRow(Base):
    __tablename__ = "digital_twins"
    twin_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.farm_id"), unique=True, nullable=False)
    current_state: Mapped[str] = mapped_column(Text, nullable=False)
    predictions: Mapped[str | None] = mapped_column(Text)
    last_update: Mapped[datetime | None] = mapped_column(DateTime)


class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"
    observation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    twin_id: Mapped[int] = mapped_column(ForeignKey("digital_twins.twin_id"), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    ndvi: Mapped[float | None] = mapped_column(Float)
    ndwi: Mapped[float | None] = mapped_column(Float)
    lai: Mapped[float | None] = mapped_column(Float)
    cloud_cover: Mapped[float | None] = mapped_column(Float)


class WeatherData(Base):
    __tablename__ = "weather_data"
    weather_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_lat: Mapped[float] = mapped_column(Float, nullable=False)
    location_lon: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    temp_max: Mapped[float | None] = mapped_column(Float)
    temp_min: Mapped[float | None] = mapped_column(Float)
    temp_avg: Mapped[float | None] = mapped_column(Float)
    rainfall: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    wind_speed: Mapped[float | None] = mapped_column(Float)


class DiseaseDetection(Base):
    __tablename__ = "disease_detections"
    detection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.farm_id"), nullable=False)
    detection_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    image_path: Mapped[str | None] = mapped_column(Text)
    disease_name_urdu: Mapped[str | None] = mapped_column(Text)
    disease_name_english: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    treatment_urdu: Mapped[str | None] = mapped_column(Text)
    treatment_english: Mapped[str | None] = mapped_column(Text)


class Buyer(Base):
    __tablename__ = "buyers"
    buyer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_person: Mapped[str | None] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(Text)
    location_lat: Mapped[float | None] = mapped_column(Float)
    location_lon: Mapped[float | None] = mapped_column(Float)
    crop_types: Mapped[str | None] = mapped_column(Text)
    price_per_ton_rice: Mapped[float | None] = mapped_column(Float)
    price_per_ton_wheat: Mapped[float | None] = mapped_column(Float)
    max_distance_km: Mapped[float] = mapped_column(Float, server_default="100")
    active: Mapped[int] = mapped_column(Integer, server_default="1")
    added_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StubbleListing(Base):
    __tablename__ = "stubble_listings"
    listing_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.farm_id"), nullable=False)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.farmer_id"), nullable=False)
    crop_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_tons: Mapped[float] = mapped_column(Float, nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float)
    market_price_per_ton: Mapped[float | None] = mapped_column(Float)
    gross_value: Mapped[float | None] = mapped_column(Float)
    platform_fee: Mapped[float | None] = mapped_column(Float)
    platform_fee_percentage: Mapped[float] = mapped_column(Float, server_default="5.0")
    net_to_farmer: Mapped[float | None] = mapped_column(Float)
    listing_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(Text, server_default="active")


class StubbleTransaction(Base):
    __tablename__ = "stubble_transactions"
    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("stubble_listings.listing_id"), nullable=False)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.buyer_id"), nullable=False)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.farmer_id"), nullable=False)
    quantity_tons: Mapped[float] = mapped_column(Float, nullable=False)
    price_per_ton: Mapped[float] = mapped_column(Float, nullable=False)
    gross_payment: Mapped[float] = mapped_column(Float, nullable=False)
    transport_cost: Mapped[float] = mapped_column(Float, nullable=False)
    platform_fee: Mapped[float] = mapped_column(Float, nullable=False)
    platform_fee_percentage: Mapped[float] = mapped_column(Float, server_default="5.0")
    net_to_farmer: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(Text, server_default="pending")


class CarbonCertificate(Base):
    __tablename__ = "carbon_certificates"
    certificate_id: Mapped[str] = mapped_column(Text, primary_key=True)  # caller-supplied text id
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("stubble_transactions.transaction_id"))
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.farmer_id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    stubble_tons: Mapped[float] = mapped_column(Float, nullable=False)
    co2_prevented_tons: Mapped[float] = mapped_column(Float, nullable=False)
    emission_factor: Mapped[float] = mapped_column(Float, nullable=False)
    verification_method: Mapped[str] = mapped_column(Text, server_default="satellite_confirmed")
    status: Mapped[str] = mapped_column(Text, server_default="verified")
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PlatformRevenue(Base):
    __tablename__ = "platform_revenue"
    revenue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    revenue_source: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_id: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    percentage: Mapped[float | None] = mapped_column(Float)
    crop_type: Mapped[str | None] = mapped_column(Text)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class B2BClient(Base):
    __tablename__ = "b2b_clients"
    client_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    client_type: Mapped[str] = mapped_column(Text, nullable=False)
    contact_person: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(Text)
    subscription_plan: Mapped[str | None] = mapped_column(Text)
    monthly_fee: Mapped[float | None] = mapped_column(Float)
    region_coverage: Mapped[str | None] = mapped_column(Text)
    active: Mapped[int] = mapped_column(Integer, server_default="1")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)


class DataReport(Base):
    __tablename__ = "data_reports"
    report_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("b2b_clients.client_id"))
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    crop_type: Mapped[str | None] = mapped_column(Text)
    report_data: Mapped[str | None] = mapped_column(Text)
    delivered: Mapped[int] = mapped_column(Integer, server_default="0")


class ImpactMetric(Base):
    __tablename__ = "impact_metrics"
    metric_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_stubble_prevented_tons: Mapped[float] = mapped_column(Float, server_default="0")
    total_co2_saved_tons: Mapped[float] = mapped_column(Float, server_default="0")
    total_farmer_earnings: Mapped[float] = mapped_column(Float, server_default="0")
    total_platform_revenue: Mapped[float] = mapped_column(Float, server_default="0")
    active_farmers: Mapped[int] = mapped_column(Integer, server_default="0")
    active_twins: Mapped[int] = mapped_column(Integer, server_default="0")
    disease_detections_count: Mapped[int] = mapped_column(Integer, server_default="0")
    transactions_count: Mapped[int] = mapped_column(Integer, server_default="0")


class AgronomyChunk(Base):
    """RAG knowledge base: chunks of advisory PDFs + their embeddings."""
    __tablename__ = "agronomy_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)        # e.g. "Punjab Pest Warning advisory"
    disease_key: Mapped[str | None] = mapped_column(Text)            # optional tag, e.g. "rice_blast"
    crop: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    last_updated: Mapped[str | None] = mapped_column(Text)           # advisory date for provenance
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))


def make_engine(database_url: str | None = None):
    """Sync engine (used for create_all and the migration script)."""
    import os
    from sqlalchemy import create_engine
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    # normalize async URL -> sync driver for create_all/migration
    url = url.replace("+asyncpg", "+psycopg2")
    return create_engine(url, pool_pre_ping=True)


def create_all(database_url: str | None = None):
    """Create the vector extension + all tables. Run once after pointing at Supabase."""
    from sqlalchemy import text
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(eng)
    print(f"✅ Created {len(Base.metadata.tables)} tables (incl. agronomy_chunks, Vector({EMBED_DIM}))")
    return eng


if __name__ == "__main__":
    create_all()