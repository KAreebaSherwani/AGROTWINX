# streamlit_app/pages/2_💰_Marketplace.py

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
from src.marketplace.stubble_marketplace import StubbleMarketplace

st.set_page_config(
    page_title="Marketplace - AgroTwinX",
    page_icon="💰",
    layout="wide"
)

# Initialize
db = Database()
marketplace = StubbleMarketplace(db)

st.title("💰 Stubble Marketplace Management")
st.markdown("Manage listings, buyers, and transactions with transparent pricing")

# Tabs for different sections
tab1, tab2, tab3, tab4 = st.tabs(["📋 Active Listings", "🏭 Buyers", "✅ Transactions", "📊 Revenue"])

# ==========================================
# TAB 1: ACTIVE LISTINGS
# ==========================================

with tab1:
    st.subheader("📋 Active Stubble Listings")
    
    # Get active listings
    listings = db.query(
        """
        SELECT 
            l.*,
            f.name as farmer_name,
            f.phone_number,
            farms.crop_type
        FROM stubble_listings l
        LEFT JOIN farmers f ON l.farmer_id = f.farmer_id
        LEFT JOIN farms ON l.farm_id = farms.farm_id
        WHERE l.status = 'active'
        ORDER BY l.listing_date DESC
        """
    )
    
    if listings:
        st.metric("Active Listings", len(listings))
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_stubble = sum([l['quantity_tons'] for l in listings])
            st.metric("Total Stubble", f"{total_stubble:.1f} tons")
        
        with col2:
            total_value = sum([l['gross_value'] for l in listings])
            st.metric("Total Value", f"Rs. {total_value:,.0f}")
        
        with col3:
            potential_revenue = sum([l['platform_fee'] for l in listings])
            st.metric("Potential Revenue", f"Rs. {potential_revenue:,.0f}")
        
        with col4:
            # Calculate average quality
            avg_quality = sum([l['quality_score'] for l in listings]) / len(listings)
            st.metric("Avg Quality", f"{avg_quality:.2f}")
        
        st.markdown("---")
        
        # Listings table
        listings_df = pd.DataFrame(listings)
        listings_df['listing_date'] = pd.to_datetime(listings_df['listing_date']).dt.strftime('%Y-%m-%d %H:%M')
        
        display_df = listings_df[[
            'listing_id', 'farmer_name', 'crop_type', 'quantity_tons', 
            'market_price_per_ton', 'gross_value', 'platform_fee', 
            'net_to_farmer', 'listing_date'
        ]].copy()
        
        display_df.columns = [
            'ID', 'Farmer', 'Crop', 'Quantity (tons)', 'Price/ton', 
            'Gross Value', 'Platform Fee (5%)', 'Net to Farmer', 'Listed Date'
        ]
        
        # Make table interactive
        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # If a listing is selected, show matches
        if event.selection and event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_listing_id = display_df.iloc[selected_idx]['ID']
            
            st.markdown("---")
            st.subheader(f"🔍 Buyer Matches for Listing #{selected_listing_id}")
            
            # Find buyers
            matches = marketplace.find_buyers(selected_listing_id)
            
            if matches:
                st.success(f"Found {len(matches)} matching buyers!")
                
                # Show matches
                for i, match in enumerate(matches, 1):
                    with st.expander(f"Match {i}: {match['buyer_name']}", expanded=(i==1)):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Buyer Details:**")
                            st.markdown(f"- **Company:** {match['buyer_name']}")
                            st.markdown(f"- **Distance:** {match['distance_km']} km")
                            st.markdown(f"- **Price:** Rs. {match['price_per_ton']}/ton")
                            st.markdown(f"- **Buyer saves:** Rs. {match['buyer_saves']:,.0f} vs traditional search")
                        
                        with col2:
                            st.markdown("**💰 Financial Breakdown:**")
                            st.markdown(f"- **Gross Payment:** Rs. {match['gross_payment']:,.0f}")
                            st.markdown(f"- **Transport Cost:** Rs. {match['transport_cost']:,.0f}")
                            st.markdown(f"- **Platform Fee (5%):** Rs. {match['platform_fee']:,.0f}")
                            st.markdown(f"- **✅ Net to Farmer:** Rs. {match['net_to_farmer']:,.0f}")
                        
                        # Action button
                        if st.button(f"✅ Create Transaction with {match['buyer_name']}", key=f"tx_{i}"):
                            # Create transaction
                            transaction = marketplace.create_transaction(
                                selected_listing_id,
                                match['buyer_id']
                            )
                            
                            if transaction:
                                st.success(f"✅ Transaction created! ID: {transaction['transaction_id']}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("Failed to create transaction")
            else:
                st.warning("No matching buyers found for this listing")
    else:
        st.info("No active listings")
        
        # Show how listings are created
        st.markdown("---")
        st.markdown("### 📝 How Listings Are Created")
        st.info("""
        Listings are **automatically created** when a farm approaches harvest (7 days or less).
        
        The system:
        1. Detects harvest is near via satellite monitoring
        2. Calculates stubble quantity from yield prediction
        3. Creates listing with transparent pricing
        4. Notifies farmer via WhatsApp
        5. Finds and matches buyers automatically
        """)

# ==========================================
# TAB 2: BUYERS MANAGEMENT
# ==========================================

with tab2:
    st.subheader("🏭 Registered Buyers")
    
    # Get all buyers
    buyers = db.query("SELECT * FROM buyers")
    
    if buyers:
        st.metric("Total Buyers", len(buyers))
        
        # Buyers table
        buyers_df = pd.DataFrame(buyers)
        
        display_df = buyers_df[[
            'buyer_id', 'company_name', 'contact_person', 'phone_number',
            'crop_types', 'price_per_ton_rice', 'price_per_ton_wheat',
            'max_distance_km', 'active'
        ]].copy()
        
        display_df.columns = [
            'ID', 'Company', 'Contact', 'Phone', 'Crops',
            'Rice Price/ton', 'Wheat Price/ton', 'Max Distance (km)', 'Active'
        ]
        
        # Active/Inactive toggle colors
        def highlight_active(val):
            return 'background-color: lightgreen' if val == 1 else 'background-color: lightcoral'
        
        st.dataframe(
            display_df.style.applymap(highlight_active, subset=['Active']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No buyers registered")
    
    st.markdown("---")
    
    # Add new buyer form
    st.subheader("➕ Add New Buyer")
    
    with st.form("add_buyer_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input("Company Name *")
            contact_person = st.text_input("Contact Person *")
            phone_number = st.text_input("Phone Number *")
            crop_types = st.multiselect("Interested Crops *", ["rice", "wheat"])
        
        with col2:
            price_rice = st.number_input("Price per ton - Rice (Rs)", min_value=0, value=3200)
            price_wheat = st.number_input("Price per ton - Wheat (Rs)", min_value=0, value=2600)
            max_distance = st.number_input("Max Distance (km)", min_value=0, value=50)
            
            st.markdown("**Location:**")
            lat = st.number_input("Latitude", value=33.60, format="%.6f")
            lon = st.number_input("Longitude", value=73.05, format="%.6f")
        
        submitted = st.form_submit_button("Add Buyer")
        
        if submitted:
            if not company_name or not contact_person or not phone_number or not crop_types:
                st.error("Please fill all required fields")
            else:
                buyer_data = {
                    'company_name': company_name,
                    'contact_person': contact_person,
                    'phone_number': phone_number,
                    'crop_types': ','.join(crop_types),
                    'price_per_ton_rice': price_rice,
                    'price_per_ton_wheat': price_wheat,
                    'max_distance_km': max_distance,
                    'location_lat': lat,
                    'location_lon': lon,
                    'active': 1
                }
                
                buyer_id = db.insert('buyers', buyer_data)
                st.success(f"✅ Buyer added successfully! ID: {buyer_id}")
                st.rerun()

# ==========================================
# TAB 3: TRANSACTIONS
# ==========================================

with tab3:
    st.subheader("✅ Completed Transactions")
    
    # Get all transactions
    transactions = db.query(
        """
        SELECT 
            t.*,
            f.name as farmer_name,
            b.company_name as buyer_name,
            farms.crop_type
        FROM stubble_transactions t
        LEFT JOIN farmers f ON t.farmer_id = f.farmer_id
        LEFT JOIN buyers b ON t.buyer_id = b.buyer_id
        LEFT JOIN stubble_listings l ON t.listing_id = l.listing_id
        LEFT JOIN farms ON l.farm_id = farms.farm_id
        ORDER BY t.transaction_date DESC
        """
    )
    
    if transactions:
        st.metric("Total Transactions", len(transactions))
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_stubble = sum([t['quantity_tons'] for t in transactions])
            st.metric("Total Stubble Sold", f"{total_stubble:.1f} tons")
        
        with col2:
            total_paid = sum([t['gross_payment'] for t in transactions])
            st.metric("Total Paid", f"Rs. {total_paid:,.0f}")
        
        with col3:
            total_fees = sum([t['platform_fee'] for t in transactions])
            st.metric("Platform Revenue", f"Rs. {total_fees:,.0f}")
        
        with col4:
            farmer_earnings = sum([t['net_to_farmer'] for t in transactions])
            st.metric("Farmer Earnings", f"Rs. {farmer_earnings:,.0f}")
        
        st.markdown("---")
        
        # Transactions table
        tx_df = pd.DataFrame(transactions)
        tx_df['transaction_date'] = pd.to_datetime(tx_df['transaction_date']).dt.strftime('%Y-%m-%d %H:%M')
        
        display_df = tx_df[[
            'transaction_id', 'farmer_name', 'buyer_name', 'crop_type',
            'quantity_tons', 'gross_payment', 'transport_cost',
            'platform_fee', 'net_to_farmer', 'status', 'transaction_date'
        ]].copy()
        
        display_df.columns = [
            'TX ID', 'Farmer', 'Buyer', 'Crop', 'Quantity (tons)',
            'Gross Payment', 'Transport', 'Platform Fee (5%)',
            'Net to Farmer', 'Status', 'Date'
        ]
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Transaction timeline
        st.markdown("---")
        st.subheader("📈 Transaction Timeline")
        
        # Group by date
        tx_df['date_only'] = pd.to_datetime(tx_df['transaction_date']).dt.date
        daily_revenue = tx_df.groupby('date_only')['platform_fee'].sum().reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily_revenue['date_only'],
            y=daily_revenue['platform_fee'],
            name='Platform Revenue',
            marker_color='green'
        ))
        
        fig.update_layout(
            title="Daily Platform Revenue",
            xaxis_title="Date",
            yaxis_title="Revenue (Rs)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("No transactions yet")

# ==========================================
# TAB 4: REVENUE ANALYTICS
# ==========================================

with tab4:
    st.subheader("📊 Revenue Analytics")
    
    # Get revenue stats
    revenue_stats = marketplace.get_revenue_stats()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Revenue",
            f"Rs. {revenue_stats['total_revenue']:,.0f}",
            help="5% commission on all transactions"
        )
    
    with col2:
        st.metric(
            "Total Transactions",
            revenue_stats['total_transactions']
        )
    
    with col3:
        st.metric(
            "Avg Commission/TX",
            f"Rs. {revenue_stats['avg_commission_per_transaction']:,.0f}"
        )
    
    st.markdown("---")
    
    # Revenue by crop type
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🌾 Revenue by Crop Type")
        
        crop_revenue = {
            'Rice': revenue_stats['rice_revenue'],
            'Wheat': revenue_stats['wheat_revenue']
        }
        
        fig = px.pie(
            values=list(crop_revenue.values()),
            names=list(crop_revenue.keys()),
            title="Revenue Distribution by Crop",
            color_discrete_map={'Rice': 'green', 'Wheat': 'orange'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📈 Revenue Growth Projection")
        
        # Mock projection data
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        current_revenue = revenue_stats['total_revenue']
        
        # Project growth (assume 20% monthly growth)
        projected = [current_revenue * (1.2 ** i) for i in range(6)]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=months,
            y=projected,
            mode='lines+markers',
            name='Projected Revenue',
            line=dict(color='green', width=3),
            marker=dict(size=10)
        ))
        
        fig.update_layout(
            title="6-Month Revenue Projection (20% growth/month)",
            xaxis_title="Month",
            yaxis_title="Revenue (Rs)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Business insights
    st.markdown("### 💡 Business Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.success(f"""
        **Current Performance:**
        - Average transaction value: Rs. {revenue_stats['total_revenue'] / max(revenue_stats['total_transactions'], 1):,.0f}
        - Platform keeps 5% commission
        - Farmers save on logistics search costs
        """)
    
    with col2:
        # Calculate potential
        active_farms = len(db.query("SELECT * FROM farms WHERE status = 'active'"))
        potential_revenue = active_farms * 5000  # Assume Rs. 5000 per farm average
        
        st.info(f"""
        **Growth Potential:**
        - Active farms: {active_farms}
        - Potential annual revenue: Rs. {potential_revenue * 2:,.0f}
        - (Assuming 2 harvest cycles/year)
        """)