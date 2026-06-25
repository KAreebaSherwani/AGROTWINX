# streamlit_app/pages/4_🌍_Impact.py

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
from src.environmental.carbon_tracker import CarbonCreditTracker

st.set_page_config(
    page_title="Environmental Impact - AgroTwinX",
    page_icon="🌍",
    layout="wide"
)

# Initialize
db = Database()
carbon_tracker = CarbonCreditTracker(db)

st.title("🌍 Environmental Impact Dashboard")
st.markdown("Tracking our contribution to a cleaner planet")

# Get impact data
impact = carbon_tracker.get_total_impact()

# Hero metrics
st.markdown("### 🎯 Total Impact")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "🌍 CO₂ Prevented",
        f"{impact['total_co2_prevented_tons']:.1f} tons",
        help="Total CO₂ emissions prevented by selling stubble instead of burning"
    )

with col2:
    st.metric(
        "🌾 Stubble Saved",
        f"{impact['total_stubble_prevented_tons']:.1f} tons",
        help="Total stubble diverted from burning"
    )

with col3:
    st.metric(
        "🚗 Cars Off Road",
        f"{impact['cars_off_road_equivalent']:.0f}",
        help="Equivalent to removing this many cars from the road for 1 year"
    )

with col4:
    st.metric(
        "🌳 Trees Planted",
        f"{impact['trees_equivalent']:,.0f}",
        help="Equivalent to planting this many trees"
    )

st.markdown("---")

# Visual impact comparison
st.markdown("### 📊 Impact Visualization")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🔥 Burning vs. Selling")
    
    # Create comparison chart
    scenarios = ['Traditional<br>Burning', 'AgroTwinX<br>Marketplace']
    
    co2_values = [impact['total_co2_prevented_tons'], 0]  # Prevented vs. Released
    air_quality = [0, 100]  # Bad vs. Good
    farmer_income = [0, impact['total_stubble_prevented_tons'] * 3000]  # No income vs. Income
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='CO₂ Released (tons)',
        x=scenarios,
        y=co2_values,
        marker_color='red',
        text=co2_values,
        textposition='auto',
    ))
    
    fig.update_layout(
        title="Environmental Impact Comparison",
        yaxis_title="CO₂ Released (tons)",
        barmode='group',
        height=400,
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Impact statement
    st.success(f"""
    **By using AgroTwinX:**
    - ✅ Zero stubble burning
    - ✅ {impact['total_co2_prevented_tons']:.1f} tons CO₂ prevented
    - ✅ Cleaner air for communities
    - ✅ Rs. {impact['total_stubble_prevented_tons'] * 3000:,.0f} earned by farmers
    """)

with col2:
    st.markdown("#### 💰 Carbon Credit Value")
    
    # Carbon credit gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=impact['carbon_credit_value_usd'],
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Carbon Credits Value (USD)"},
        delta={'reference': impact['carbon_credit_value_usd'] * 0.8},
        gauge={
            'axis': {'range': [None, impact['carbon_credit_value_usd'] * 1.5]},
            'bar': {'color': "darkgreen"},
            'steps': [
                {'range': [0, impact['carbon_credit_value_usd'] * 0.5], 'color': "lightgray"},
                {'range': [impact['carbon_credit_value_usd'] * 0.5, impact['carbon_credit_value_usd']], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "green", 'width': 4},
                'thickness': 0.75,
                'value': impact['carbon_credit_value_usd']
            }
        }
    ))
    
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
    
    st.info(f"""
    **Potential Revenue Stream:**
    - Carbon credit market value: ${impact['carbon_credit_value_usd']:,.0f}
    - In PKR: Rs. {impact['carbon_credit_value_pkr']:,.0f}
    - Certificates issued: {impact['certificates_issued']}
    - Ready for international carbon markets
    """)

st.markdown("---")

# Carbon certificates
st.markdown("### 📜 Carbon Certificates Issued")

certificates = db.query("SELECT * FROM carbon_certificates ORDER BY date DESC")

if certificates:
    # Summary stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Certificates", len(certificates))
    
    with col2:
        avg_co2 = sum([c['co2_prevented_tons'] for c in certificates]) / len(certificates)
        st.metric("Avg CO₂ per Certificate", f"{avg_co2:.2f} tons")
    
    with col3:
        verified = len([c for c in certificates if c['status'] == 'verified'])
        st.metric("Verified Certificates", f"{verified}/{len(certificates)}")
    
    st.markdown("---")
    
    # Certificates table
    cert_df = pd.DataFrame(certificates)
    cert_df['date'] = pd.to_datetime(cert_df['date']).dt.strftime('%Y-%m-%d')
    
    # Get farmer names
    cert_df['farmer_name'] = cert_df['farmer_id'].apply(
        lambda x: db.get('farmers', 'farmer_id', x)['name'] if db.get('farmers', 'farmer_id', x) else 'Unknown'
    )
    
    display_df = cert_df[[
        'certificate_id', 'farmer_name', 'date', 'stubble_tons',
        'co2_prevented_tons', 'verification_method', 'status'
    ]].copy()
    
    display_df.columns = [
        'Certificate ID', 'Farmer', 'Date', 'Stubble (tons)',
        'CO₂ Prevented (tons)', 'Verification', 'Status'
    ]
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Time series
    st.markdown("### 📈 CO₂ Prevention Over Time")
    
    cert_df['date'] = pd.to_datetime(cert_df['date'])
    cert_df = cert_df.sort_values('date')
    cert_df['cumulative_co2'] = cert_df['co2_prevented_tons'].cumsum()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=cert_df['date'],
        y=cert_df['cumulative_co2'],
        mode='lines+markers',
        name='Cumulative CO₂ Prevented',
        line=dict(color='green', width=3),
        fill='tozeroy',
        fillcolor='rgba(0,128,0,0.2)'
    ))
    
    fig.update_layout(
        title="Cumulative CO₂ Prevention",
        xaxis_title="Date",
        yaxis_title="CO₂ Prevented (tons)",
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No carbon certificates issued yet")

st.markdown("---")

# Regional impact
st.markdown("### 🗺️ Impact by Region")

# Get transaction data with locations
transactions = db.query("""
    SELECT 
        t.*,
        f.location_lat,
        f.location_lon,
        f.district
    FROM stubble_transactions t
    LEFT JOIN farmers f ON t.farmer_id = f.farmer_id
""")

if transactions:
    # Impact by district
    district_impact = {}
    
    for tx in transactions:
        district = tx.get('district', 'Unknown')
        
        # Get certificate for this transaction
        cert = db.query(
            "SELECT * FROM carbon_certificates WHERE transaction_id = ?",
            (tx['transaction_id'],)
        )
        
        if cert:
            co2 = cert[0]['co2_prevented_tons']
            if district not in district_impact:
                district_impact[district] = {'co2': 0, 'transactions': 0}
            
            district_impact[district]['co2'] += co2
            district_impact[district]['transactions'] += 1
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Bar chart by district
        districts = list(district_impact.keys())
        co2_values = [district_impact[d]['co2'] for d in districts]
        
        fig = px.bar(
            x=districts,
            y=co2_values,
            title="CO₂ Prevention by District",
            labels={'x': 'District', 'y': 'CO₂ Prevented (tons)'},
            color=co2_values,
            color_continuous_scale='Greens'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Transaction count
        tx_counts = [district_impact[d]['transactions'] for d in districts]
        
        fig = px.pie(
            values=tx_counts,
            names=districts,
            title="Transactions by District"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Map visualization
    st.markdown("### 🗺️ Impact Map")
    
    import folium
    from streamlit_folium import st_folium
    
    m = folium.Map(
        location=[33.74, 73.13],
        zoom_start=10
    )
    
    for tx in transactions:
        if tx.get('location_lat') and tx.get('location_lon'):
            # Get CO₂ prevented
            cert = db.query(
                "SELECT * FROM carbon_certificates WHERE transaction_id = ?",
                (tx['transaction_id'],)
            )
            
            if cert:
                co2 = cert[0]['co2_prevented_tons']
                
                folium.CircleMarker(
                    location=[tx['location_lat'], tx['location_lon']],
                    radius=co2 * 2,  # Scale by CO₂
                    popup=f"CO₂ Prevented: {co2:.2f} tons",
                    color='green',
                    fill=True,
                    fillColor='green',
                    fillOpacity=0.6
                ).add_to(m)
    
    st_folium(m, width=1400, height=500)

st.markdown("---")

# Future projections
st.markdown("### 🎯 Future Impact Projections")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📈 Projected CO₂ Prevention")
    
    months = ['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Month 6']
    current_co2 = impact['total_co2_prevented_tons']
    
    # Project 25% growth per month
    projected_co2 = [current_co2 * (1.25 ** i) for i in range(6)]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=months,
        y=projected_co2,
        mode='lines+markers',
        name='Projected CO₂ Prevention',
        line=dict(color='green', width=3),
        marker=dict(size=10),
        fill='tozeroy',
        fillcolor='rgba(0,128,0,0.2)'
    ))
    
    fig.update_layout(
        title="6-Month CO₂ Prevention Projection",
        xaxis_title="Month",
        yaxis_title="CO₂ Prevented (tons)",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("#### 💰 Projected Carbon Credit Value")
    
    from config import CARBON_CREDIT_PRICE_USD, USD_TO_PKR
    
    projected_value_usd = [co2 * CARBON_CREDIT_PRICE_USD for co2 in projected_co2]
    projected_value_pkr = [val * USD_TO_PKR for val in projected_value_usd]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=months,
        y=projected_value_pkr,
        marker_color='green',
        name='Projected Value (PKR)',
        text=[f"Rs. {val/1000:.0f}K" for val in projected_value_pkr],
        textposition='auto'
    ))
    
    fig.update_layout(
        title="6-Month Carbon Credit Value Projection",
        xaxis_title="Month",
        yaxis_title="Value (Rs)",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Call to action
st.markdown("---")

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.success("""
    ### 🌟 Our Mission
    
    **AgroTwinX is committed to:**
    - ✅ Eliminating stubble burning in Pakistan
    - ✅ Creating economic value from agricultural waste
    - ✅ Fighting climate change through technology
    - ✅ Empowering farmers with sustainable practices
    
    **Together, we're building a cleaner, greener future! 🌍**
    """)