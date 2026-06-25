# streamlit_app/pages/3_📈_Analytics.py

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.utils.database import Database
from src.analytics.data_insights import DataInsightsEngine

st.set_page_config(
    page_title="Analytics - AgroTwinX",
    page_icon="📈",
    layout="wide"
)

# Initialize
db = Database()
insights_engine = DataInsightsEngine(db)

st.title("📈 Business Analytics & Insights")
st.markdown("Data-driven insights for better decision making")

# Date range selector
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    start_date = st.date_input(
        "Start Date",
        value=datetime.now() - timedelta(days=30)
    )

with col2:
    end_date = st.date_input(
        "End Date",
        value=datetime.now()
    )

with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

st.markdown("---")

# Key Performance Indicators
st.subheader("📊 Key Performance Indicators (KPIs)")

col1, col2, col3, col4, col5 = st.columns(5)

# Get data
farmers = db.query("SELECT * FROM farmers WHERE active = 1")
farms = db.query("SELECT * FROM farms WHERE status = 'active'")
transactions = db.query("SELECT * FROM stubble_transactions")
twins = db.query("SELECT * FROM digital_twins")

with col1:
    # Growth rate
    last_week = len([f for f in farmers if (datetime.now() - datetime.fromisoformat(f['registered_date'])).days <= 7])
    growth_rate = (last_week / max(len(farmers), 1)) * 100
    
    st.metric(
        "👨‍🌾 Active Farmers",
        len(farmers),
        delta=f"+{growth_rate:.1f}% this week"
    )

with col2:
    total_area = sum([f['area_acres'] for f in farms])
    st.metric(
        "🌾 Total Area",
        f"{total_area:.0f} acres",
        delta="+5.2%"
    )

with col3:
    if transactions:
        total_revenue = sum([t['platform_fee'] for t in transactions])
        st.metric(
            "💰 Total Revenue",
            f"Rs. {total_revenue:,.0f}",
            delta=f"+{len(transactions)} transactions"
        )
    else:
        st.metric("💰 Total Revenue", "Rs. 0", delta="No data")

with col4:
    # Calculate average health
    if twins:
        health_scores = []
        for twin in twins:
            state = json.loads(twin['current_state'])
            health_scores.append(state.get('health_score', 50))
        avg_health = np.mean(health_scores)
        
        st.metric(
            "🌿 Avg Farm Health",
            f"{avg_health:.1f}%",
            delta="+2.3%"
        )
    else:
        st.metric("🌿 Avg Farm Health", "N/A", delta="No data")

with col5:
    # Get disease detections
    detections = db.query("SELECT * FROM disease_detections")
    st.metric(
        "🦠 Disease Detections",
        len(detections),
        delta=f"{len([d for d in detections if d['severity'] == 'severe'])} severe"
    )

st.markdown("---")

# Tabs for different analytics
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Farm Analytics",
    "💰 Financial Analytics",
    "🌍 Regional Insights",
    "🎯 Predictions"
])

# ==========================================
# TAB 1: FARM ANALYTICS
# ==========================================

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🌾 Crop Distribution")
        
        # Get crop counts
        crop_counts = {}
        for farm in farms:
            crop = farm['crop_type']
            crop_counts[crop] = crop_counts.get(crop, 0) + 1
        
        fig = px.pie(
            values=list(crop_counts.values()),
            names=[c.title() for c in crop_counts.keys()],
            title="Farms by Crop Type",
            color_discrete_map={'Rice': 'green', 'Wheat': 'orange'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📈 Health Score Distribution")
        
        if twins:
            health_scores = []
            for twin in twins:
                state = json.loads(twin['current_state'])
                health_scores.append(state.get('health_score', 50))
            
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=health_scores,
                nbinsx=20,
                marker_color='green',
                opacity=0.7
            ))
            
            fig.update_layout(
                title="Distribution of Farm Health Scores",
                xaxis_title="Health Score",
                yaxis_title="Number of Farms",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Growth stage analysis
    st.markdown("### 📊 Growth Stage Analysis")
    
    if twins:
        stage_counts = {}
        for twin in twins:
            state = json.loads(twin['current_state'])
            stage = state.get('stage', 'unknown')
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        fig = px.bar(
            x=list(stage_counts.keys()),
            y=list(stage_counts.values()),
            title="Farms by Growth Stage",
            labels={'x': 'Growth Stage', 'y': 'Number of Farms'},
            color=list(stage_counts.values()),
            color_continuous_scale='Greens'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Yield predictions
    st.markdown("### 🎯 Yield Predictions")
    
    if twins:
        yield_data = []
        
        for twin in twins:
            predictions = json.loads(twin['predictions'])
            farm = db.get('farms', 'farm_id', twin['farm_id'])
            
            if predictions.get('expected_yield_maunds'):
                yield_data.append({
                    'farm_id': twin['farm_id'],
                    'crop': farm['crop_type'],
                    'area_acres': farm['area_acres'],
                    'expected_yield': predictions['expected_yield_maunds'],
                    'yield_per_acre': predictions['expected_yield_maunds'] / farm['area_acres']
                })
        
        if yield_data:
            df_yield = pd.DataFrame(yield_data)
            
            fig = px.scatter(
                df_yield,
                x='area_acres',
                y='yield_per_acre',
                size='expected_yield',
                color='crop',
                title="Yield Efficiency (Yield per Acre vs Farm Size)",
                labels={
                    'area_acres': 'Farm Size (acres)',
                    'yield_per_acre': 'Yield per Acre (maunds)',
                    'crop': 'Crop Type'
                },
                color_discrete_map={'rice': 'green', 'wheat': 'orange'}
            )
            
            st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 2: FINANCIAL ANALYTICS
# ==========================================

with tab2:
    st.markdown("### 💰 Revenue Overview")
    
    if transactions:
        # Revenue metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_gross = sum([t['gross_payment'] for t in transactions])
            st.metric("Total Gross Value", f"Rs. {total_gross:,.0f}")
        
        with col2:
            total_fees = sum([t['platform_fee'] for t in transactions])
            st.metric("Platform Revenue (5%)", f"Rs. {total_fees:,.0f}")
        
        with col3:
            farmer_earnings = sum([t['net_to_farmer'] for t in transactions])
            st.metric("Total Farmer Earnings", f"Rs. {farmer_earnings:,.0f}")
        
        st.markdown("---")
        
        # Revenue breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Revenue by Crop Type")
            
            crop_revenue = {}
            for t in transactions:
                # Get crop type from listing
                listing = db.get('stubble_listings', 'listing_id', t['listing_id'])
                if listing:
                    crop = listing['crop_type']
                    crop_revenue[crop] = crop_revenue.get(crop, 0) + t['platform_fee']
            
            fig = px.bar(
                x=[c.title() for c in crop_revenue.keys()],
                y=list(crop_revenue.values()),
                title="Platform Revenue by Crop",
                labels={'x': 'Crop Type', 'y': 'Revenue (Rs)'},
                color=list(crop_revenue.values()),
                color_continuous_scale='Greens'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 📈 Cumulative Revenue")
            
            # Sort transactions by date
            tx_df = pd.DataFrame(transactions)
            tx_df['transaction_date'] = pd.to_datetime(tx_df['transaction_date'])
            tx_df = tx_df.sort_values('transaction_date')
            
            # Calculate cumulative revenue
            tx_df['cumulative_revenue'] = tx_df['platform_fee'].cumsum()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=tx_df['transaction_date'],
                y=tx_df['cumulative_revenue'],
                mode='lines+markers',
                name='Cumulative Revenue',
                line=dict(color='green', width=3),
                fill='tozeroy',
                fillcolor='rgba(0,255,0,0.1)'
            ))
            
            fig.update_layout(
                title="Revenue Growth Over Time",
                xaxis_title="Date",
                yaxis_title="Cumulative Revenue (Rs)",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Transaction size distribution
        st.markdown("### 💵 Transaction Size Distribution")
        
        fig = go.Figure()
        fig.add_trace(go.Box(
            y=[t['gross_payment'] for t in transactions],
            name='Gross Payment',
            marker_color='lightblue'
        ))
        fig.add_trace(go.Box(
            y=[t['net_to_farmer'] for t in transactions],
            name='Net to Farmer',
            marker_color='green'
        ))
        fig.add_trace(go.Box(
            y=[t['platform_fee'] for t in transactions],
            name='Platform Fee',
            marker_color='orange'
        ))
        
        fig.update_layout(
            title="Transaction Value Distribution",
            yaxis_title="Amount (Rs)",
            showlegend=True,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("No transaction data available yet")

# ==========================================
# TAB 3: REGIONAL INSIGHTS
# ==========================================

with tab3:
    st.markdown("### 🌍 Regional Distribution")
    
    # Group farmers by district
    district_counts = {}
    for farmer in farmers:
        district = farmer.get('district', 'Unknown')
        district_counts[district] = district_counts.get(district, 0) + 1
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            x=list(district_counts.keys()),
            y=list(district_counts.values()),
            title="Farmers by District",
            labels={'x': 'District', 'y': 'Number of Farmers'},
            color=list(district_counts.values()),
            color_continuous_scale='Greens'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.pie(
            values=list(district_counts.values()),
            names=list(district_counts.keys()),
            title="Market Share by District"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Geographic heatmap
    st.markdown("### 🗺️ Farm Density Heatmap")
    
    if farmers:
        import folium
        from folium.plugins import HeatMap
        from streamlit_folium import st_folium
        
        # Create base map
        m = folium.Map(
            location=[33.74, 73.13],
            zoom_start=10
        )
        
        # Prepare heatmap data
        heat_data = [[f['location_lat'], f['location_lon']] for f in farmers]
        
        # Add heatmap
        HeatMap(heat_data, radius=15).add_to(m)
        
        # Display
        st_folium(m, width=1400, height=500)

# ==========================================
# TAB 4: PREDICTIONS & FORECASTS
# ==========================================

with tab4:
    st.markdown("### 🎯 Business Forecasts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📈 Farmer Growth Projection")
        
        # Calculate growth rate
        if len(farmers) > 1:
            # Mock growth projection
            months = ['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Month 6']
            current_farmers = len(farmers)
            
            # Assume 15% monthly growth
            projected = [current_farmers * (1.15 ** i) for i in range(6)]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=months,
                y=projected,
                mode='lines+markers',
                name='Projected Farmers',
                line=dict(color='blue', width=3),
                marker=dict(size=10)
            ))
            
            fig.update_layout(
                title="6-Month Farmer Growth (15% monthly)",
                xaxis_title="Month",
                yaxis_title="Number of Farmers",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 💰 Revenue Forecast")
        
        if transactions:
            months = ['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Month 6']
            current_monthly = sum([t['platform_fee'] for t in transactions])
            
            # Project 20% growth
            projected = [current_monthly * (1.20 ** i) for i in range(6)]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=months,
                y=projected,
                marker_color='green',
                name='Projected Revenue'
            ))
            
            fig.update_layout(
                title="6-Month Revenue Projection (20% growth)",
                xaxis_title="Month",
                yaxis_title="Revenue (Rs)",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Harvest calendar
    st.markdown("### 📅 Upcoming Harvest Calendar")
    
    if twins:
        harvest_data = []
        
        for twin in twins:
            predictions = json.loads(twin['predictions'])
            farm = db.get('farms', 'farm_id', twin['farm_id'])
            farmer = db.get('farmers', 'farmer_id', farm['farmer_id'])
            
            days_to_harvest = predictions.get('days_to_harvest')
            
            if days_to_harvest and days_to_harvest <= 60:
                harvest_date = datetime.now() + timedelta(days=days_to_harvest)
                
                harvest_data.append({
                    'Farmer': farmer['name'],
                    'Crop': farm['crop_type'].title(),
                    'Area (acres)': farm['area_acres'],
                    'Days Until Harvest': days_to_harvest,
                    'Expected Date': harvest_date.strftime('%Y-%m-%d'),
                    'Expected Stubble (tons)': predictions.get('stubble_tons', 0),
                    'Est. Revenue': f"Rs. {predictions.get('stubble_value', 0):,.0f}"
                })
        
        if harvest_data:
            df_harvest = pd.DataFrame(harvest_data)
            df_harvest = df_harvest.sort_values('Days Until Harvest')
            
            st.dataframe(
                df_harvest,
                use_container_width=True,
                hide_index=True
            )
            
            # Timeline visualization
            fig = go.Figure()
            
            for i, row in df_harvest.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row['Days Until Harvest']],
                    y=[row['Farmer']],
                    mode='markers+text',
                    marker=dict(
                        size=20,
                        color='green' if row['Crop'] == 'Rice' else 'orange'
                    ),
                    text=[row['Crop']],
                    textposition='top center',
                    name=row['Farmer'],
                    showlegend=False
                ))
            
            fig.update_layout(
                title="Harvest Timeline",
                xaxis_title="Days Until Harvest",
                yaxis_title="Farmer",
                height=max(400, len(df_harvest) * 40),
                hovermode='closest'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No harvests expected in the next 60 days")