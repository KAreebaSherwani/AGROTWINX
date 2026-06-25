# streamlit_app/app.py

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database
from config import *

# Page config
st.set_page_config(
    page_title="AgroTwinX - Digital Farm Management",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    h1 {
        color: #2c5f2d;
    }
    .big-font {
        font-size: 24px !important;
        font-weight: bold;
    }
    .highlight {
        background-color: #d4edda;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
@st.cache_resource
def init_database():
    return Database()

db = init_database()

# Sidebar
with st.sidebar:
    st.image("https://via.placeholder.com/200x80/2c5f2d/ffffff?text=AgroTwinX", use_container_width=True)
    st.markdown("---")
    st.markdown("### 🌾 Digital Farm Management")
    st.markdown("Real-time monitoring, AI-powered insights, and marketplace automation.")
    st.markdown("---")
    
    # Quick stats in sidebar
    st.markdown("### 📊 Quick Stats")
    
    total_farmers = len(db.query("SELECT * FROM farmers WHERE active = 1"))
    total_farms = len(db.query("SELECT * FROM farms WHERE status = 'active'"))
    
    st.metric("Active Farmers", total_farmers)
    st.metric("Active Farms", total_farms)

# Main page
st.title("🌾 AgroTwinX Dashboard")
st.markdown("### Welcome to the Digital Farm Management Platform")

# Key metrics row
col1, col2, col3, col4 = st.columns(4)

with col1:
    farmers = db.query("SELECT * FROM farmers WHERE active = 1")
    st.metric(
        label="👨‍🌾 Total Farmers",
        value=len(farmers),
        delta="+5 this week"
    )

with col2:
    farms = db.query("SELECT * FROM farms WHERE status = 'active'")
    total_acres = sum([f['area_acres'] for f in farms])
    st.metric(
        label="🌾 Total Area",
        value=f"{total_acres:.0f} acres",
        delta="+12 acres"
    )

with col3:
    transactions = db.query("SELECT * FROM stubble_transactions")
    if transactions:
        total_revenue = sum([t['platform_fee'] for t in transactions])
        st.metric(
            label="💰 Platform Revenue",
            value=f"Rs. {total_revenue:,.0f}",
            delta=f"+Rs. {total_revenue*0.15:,.0f}"
        )
    else:
        st.metric(
            label="💰 Platform Revenue",
            value="Rs. 0",
            delta="No transactions yet"
        )

with col4:
    # Get carbon certificates
    certificates = db.query("SELECT * FROM carbon_certificates")
    if certificates:
        total_co2 = sum([c['co2_prevented_tons'] for c in certificates])
        st.metric(
            label="🌍 CO₂ Prevented",
            value=f"{total_co2:.1f} tons",
            delta=f"{len(certificates)} certificates"
        )
    else:
        st.metric(
            label="🌍 CO₂ Prevented",
            value="0 tons",
            delta="No data"
        )

st.markdown("---")

# Recent activity
st.subheader("📋 Recent Activity")

tab1, tab2, tab3 = st.tabs(["🆕 New Farmers", "💰 Transactions", "🦠 Disease Detections"])

with tab1:
    recent_farmers = db.query(
        """
        SELECT * FROM farmers 
        ORDER BY registered_date DESC 
        LIMIT 10
        """
    )
    
    if recent_farmers:
        df = pd.DataFrame(recent_farmers)
        df['registered_date'] = pd.to_datetime(df['registered_date']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            df[['name', 'phone_number', 'district', 'village', 'registered_date']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No farmers registered yet")

with tab2:
    recent_transactions = db.query(
        """
        SELECT 
            t.*,
            f.name as farmer_name,
            b.company_name as buyer_name
        FROM stubble_transactions t
        LEFT JOIN farmers f ON t.farmer_id = f.farmer_id
        LEFT JOIN buyers b ON t.buyer_id = b.buyer_id
        ORDER BY t.transaction_date DESC
        LIMIT 10
        """
    )
    
    if recent_transactions:
        df = pd.DataFrame(recent_transactions)
        df['transaction_date'] = pd.to_datetime(df['transaction_date']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            df[['farmer_name', 'buyer_name', 'quantity_tons', 'net_to_farmer', 'platform_fee', 'transaction_date']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No transactions yet")

with tab3:
    recent_detections = db.query(
        """
        SELECT 
            d.*,
            f.name as farmer_name,
            fm.crop_type
        FROM disease_detections d
        LEFT JOIN farms fm ON d.farm_id = fm.farm_id
        LEFT JOIN farmers f ON fm.farmer_id = f.farmer_id
        ORDER BY d.detection_date DESC
        LIMIT 10
        """
    )
    
    if recent_detections:
        df = pd.DataFrame(recent_detections)
        df['detection_date'] = pd.to_datetime(df['detection_date']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Color-code severity
        def severity_color(severity):
            colors = {
                'mild': '🟡',
                'moderate': '🟠',
                'severe': '🔴'
            }
            return colors.get(severity, '⚪')
        
        df['severity_icon'] = df['severity'].apply(severity_color)
        
        st.dataframe(
            df[['severity_icon', 'farmer_name', 'crop_type', 'disease_name_english', 'confidence', 'detection_date']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No disease detections yet")

# Map preview
st.markdown("---")
st.subheader("🗺️ Farm Locations")

# Get all farms with locations
farms_with_location = db.query("""
    SELECT 
        f.*,
        farms.crop_type,
        farms.area_acres
    FROM farmers f
    LEFT JOIN farms ON f.farmer_id = farms.farmer_id
    WHERE f.active = 1 AND farms.status = 'active'
""")

if farms_with_location:
    import folium
    from streamlit_folium import st_folium
    
    # Create map centered on Taxila
    m = folium.Map(
        location=[33.74, 73.13],
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Add farm markers
    for farm in farms_with_location:
        # Color by crop type
        color = 'green' if farm['crop_type'] == 'rice' else 'orange'
        
        folium.CircleMarker(
            location=[farm['location_lat'], farm['location_lon']],
            radius=8,
            popup=f"""
                <b>{farm['name']}</b><br>
                Crop: {farm['crop_type']}<br>
                Area: {farm['area_acres']} acres
            """,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7
        ).add_to(m)
    
    # Display map
    st_folium(m, width=1400, height=400)
else:
    st.info("No farms to display on map")

# Quick actions
st.markdown("---")
st.subheader("⚡ Quick Actions")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🌾 View All Farms", use_container_width=True):
        st.switch_page("pages/1_📊_Farm_Monitor.py")

with col2:
    if st.button("💰 Manage Marketplace", use_container_width=True):
        st.switch_page("pages/2_💰_Marketplace.py")

with col3:
    if st.button("📈 View Analytics", use_container_width=True):
        st.switch_page("pages/3_📈_Analytics.py")

with col4:
    if st.button("🌍 Impact Report", use_container_width=True):
        st.switch_page("pages/4_🌍_Impact.py")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; padding: 20px;'>
    <p>AgroTwinX - Digital Farm Management Platform</p>
    <p>Built with ❤️ for Pakistani farmers</p>
</div>
""", unsafe_allow_html=True)