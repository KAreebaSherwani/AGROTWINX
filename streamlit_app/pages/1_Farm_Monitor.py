# streamlit_app/pages/1_📊_Farm_Monitor.py

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import json
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.utils.database import Database
from src.models.digital_twin import DigitalTwin

st.set_page_config(
    page_title="Farm Monitor - AgroTwinX",
    page_icon="📊",
    layout="wide"
)

# Initialize
db = Database()

st.title("📊 Farm Monitoring Dashboard")
st.markdown("Real-time crop health and growth tracking")

# Filters
col1, col2, col3 = st.columns(3)

with col1:
    crop_filter = st.selectbox(
        "Crop Type",
        ["All", "Rice", "Wheat"]
    )

with col2:
    health_filter = st.selectbox(
        "Health Status",
        ["All", "Excellent (80-100%)", "Good (60-80%)", "Fair (40-60%)", "Poor (<40%)"]
    )

with col3:
    stage_filter = st.selectbox(
        "Growth Stage",
        ["All", "Early", "Mid", "Late"]
    )

# Get all farms
farms = db.query("SELECT * FROM farms WHERE status = 'active'")

# Apply filters
if crop_filter != "All":
    farms = [f for f in farms if f['crop_type'] == crop_filter.lower()]

st.markdown("---")

# Summary stats
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Farms", len(farms))

with col2:
    total_area = sum([f['area_acres'] for f in farms])
    st.metric("Total Area", f"{total_area:.0f} acres")

with col3:
    # Calculate average health
    twins = db.query("SELECT * FROM digital_twins")
    if twins:
        health_scores = []
        for twin_data in twins:
            state = json.loads(twin_data['current_state'])
            health_scores.append(state.get('health_score', 50))
        
        avg_health = sum(health_scores) / len(health_scores)
        st.metric("Avg Health", f"{avg_health:.0f}%")
    else:
        st.metric("Avg Health", "N/A")

with col4:
    # Count farms near harvest
    near_harvest = 0
    for twin_data in twins:
        predictions = json.loads(twin_data['predictions'])
        days = predictions.get('days_to_harvest', 999)
        if days <= 14:
            near_harvest += 1
    
    st.metric("Near Harvest", near_harvest, help="Farms within 14 days of harvest")

st.markdown("---")

# Farm list with details
st.subheader("🌾 Active Farms")

# Create detailed farm table
farm_details = []

for farm in farms:
    # Get farmer info
    farmer = db.get('farmers', 'farmer_id', farm['farmer_id'])
    
    # Get twin data
    twin_data = db.query(
        "SELECT * FROM digital_twins WHERE farm_id = ?",
        (farm['farm_id'],)
    )
    
    if twin_data:
        twin = twin_data[0]
        state = json.loads(twin['current_state'])
        predictions = json.loads(twin['predictions'])
        
        # Health emoji
        health = state.get('health_score', 50)
        if health >= 80:
            health_icon = '🟢'
        elif health >= 60:
            health_icon = '🟡'
        else:
            health_icon = '🔴'
        
        farm_details.append({
            'Farm ID': farm['farm_id'],
            'Farmer': farmer['name'] if farmer else 'Unknown',
            'Crop': farm['crop_type'].title(),
            'Area (acres)': farm['area_acres'],
            'Health': f"{health_icon} {health}%",
            'Stage': state.get('stage', 'N/A'),
            'Days to Harvest': predictions.get('days_to_harvest', 'N/A'),
            'Expected Yield (maunds)': predictions.get('expected_yield_maunds', 'Calculating...'),
            'Stubble Value': f"Rs. {predictions.get('stubble_value', 0):,.0f}",
            'Last Update': state.get('last_update', 'Never')
        })

if farm_details:
    df = pd.DataFrame(farm_details)
    
    # Make Farm ID clickable (selection)
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    # If a farm is selected, show detailed view
    if event.selection and event.selection.rows:
        selected_idx = event.selection.rows[0]
        selected_farm_id = df.iloc[selected_idx]['Farm ID']
        
        st.markdown("---")
        st.subheader(f"📊 Detailed View - Farm #{selected_farm_id}")
        
        # Load full twin data
        twin_data = db.query(
            "SELECT * FROM digital_twins WHERE farm_id = ?",
            (selected_farm_id,)
        )[0]
        
        state = json.loads(twin_data['current_state'])
        predictions = json.loads(twin_data['predictions'])
        history = json.loads(twin_data.get('satellite_history', '[]'))
        
        # Twin details in columns
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📈 Current Status")
            
            health = state.get('health_score', 50)
            
            # Health gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=health,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Health Score"},
                delta={'reference': 70},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkgreen"},
                    'steps': [
                        {'range': [0, 40], 'color': "lightcoral"},
                        {'range': [40, 60], 'color': "lightyellow"},
                        {'range': [60, 80], 'color': "lightgreen"},
                        {'range': [80, 100], 'color': "green"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            # Key metrics
            st.markdown("**Growth Stage:** " + state.get('stage', 'N/A'))
            st.markdown("**Days Since Planting:** " + str(state.get('days_since_planting', 'N/A')))
            st.markdown("**Current NDVI:** " + str(state.get('ndvi_current', 'N/A')))
            st.markdown("**Current NDWI:** " + str(state.get('ndwi_current', 'N/A')))
        
        with col2:
            st.markdown("### 🎯 Predictions")
            
            st.metric("Days to Harvest", predictions.get('days_to_harvest', 'N/A'))
            st.metric("Expected Yield", f"{predictions.get('expected_yield_maunds', 'Calculating...')} maunds")
            st.metric("Stubble Quantity", f"{predictions.get('stubble_tons', 0):.1f} tons")
            st.metric("Stubble Value", f"Rs. {predictions.get('stubble_value', 0):,.0f}")
            
            # Carbon credit potential
            carbon = predictions.get('carbon_credit_potential', {})
            if carbon:
                st.metric("Carbon Credits", f"Rs. {carbon.get('value_pkr', 0):,.0f}")
        
        # NDVI time series
        if history:
            st.markdown("### 📊 NDVI Timeline")
            
            dates = [h['date'] for h in history]
            ndvi_values = [h['ndvi'] for h in history]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates,
                y=ndvi_values,
                mode='lines+markers',
                name='NDVI',
                line=dict(color='green', width=2),
                marker=dict(size=8)
            ))
            
            fig.update_layout(
                title="Vegetation Index Over Time",
                xaxis_title="Date",
                yaxis_title="NDVI",
                hovermode='x unified',
                height=300
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Alerts
        alerts = state.get('alerts', [])
        if alerts:
            st.markdown("### ⚠️ Active Alerts")
            
            for alert in alerts:
                severity = alert.get('severity', 'medium')
                
                if severity == 'high':
                    st.error(f"🔴 **{alert.get('type', 'Alert')}:** {alert.get('message_english', '')}")
                elif severity == 'medium':
                    st.warning(f"🟠 **{alert.get('type', 'Alert')}:** {alert.get('message_english', '')}")
                else:
                    st.info(f"🟡 **{alert.get('type', 'Alert')}:** {alert.get('message_english', '')}")

else:
    st.info("No farms to display")

# Health distribution chart
st.markdown("---")
st.subheader("📊 Farm Health Distribution")

if twins:
    health_data = []
    for twin_data in twins:
        state = json.loads(twin_data['current_state'])
        health = state.get('health_score', 50)
        
        if health >= 80:
            category = 'Excellent'
        elif health >= 60:
            category = 'Good'
        elif health >= 40:
            category = 'Fair'
        else:
            category = 'Poor'
        
        health_data.append(category)
    
    # Count by category
    df_health = pd.DataFrame({'Health': health_data})
    health_counts = df_health['Health'].value_counts()
    
    fig = px.pie(
        values=health_counts.values,
        names=health_counts.index,
        title="Farm Health Distribution",
        color_discrete_map={
            'Excellent': 'green',
            'Good': 'lightgreen',
            'Fair': 'yellow',
            'Poor': 'red'
        }
    )
    
    st.plotly_chart(fig, use_container_width=True)