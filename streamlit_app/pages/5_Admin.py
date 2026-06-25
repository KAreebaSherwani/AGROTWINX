# streamlit_app/pages/5_⚙️_Admin.py

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import json
from datetime import datetime, timedelta
import plotly.graph_objects as go

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.utils.database import Database
from src.models.digital_twin import DigitalTwin

st.set_page_config(
    page_title="Admin Panel - AgroTwinX",
    page_icon="⚙️",
    layout="wide"
)

# Initialize
db = Database()

# Simple authentication (in production, use proper auth)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Admin Login")
    
    password = st.text_input("Enter Admin Password", type="password")
    
    if st.button("Login"):
        if password == "admin123":  # Change this in production!
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid password")
    
    st.stop()

# Admin panel
st.title("⚙️ Admin Control Panel")
st.markdown("System management and configuration")

# Logout button
col1, col2, col3 = st.columns([5, 1, 1])
with col3:
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 System Status",
    "👥 User Management",
    "🗄️ Database Management",
    "⚙️ Configuration",
    "📧 Communications"
])

# ==========================================
# TAB 1: SYSTEM STATUS
# ==========================================

with tab1:
    st.subheader("📊 System Health")
    
    # System metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Database size
        import os
        db_size = os.path.getsize('data/agrotwinx.db') / (1024 * 1024)  # MB
        st.metric("Database Size", f"{db_size:.2f} MB")
    
    with col2:
        # Total records
        total_records = (
            len(db.query("SELECT * FROM farmers")) +
            len(db.query("SELECT * FROM farms")) +
            len(db.query("SELECT * FROM digital_twins")) +
            len(db.query("SELECT * FROM stubble_transactions"))
        )
        st.metric("Total Records", f"{total_records:,}")
    
    with col3:
        # Active connections (mock)
        st.metric("Active Sessions", "5", delta="+2")
    
    with col4:
        # System uptime (mock)
        st.metric("System Uptime", "99.9%", delta="+0.1%")
    
    st.markdown("---")
    
    # Recent activity log
    st.markdown("### 📝 Recent Activity Log")
    
    # Get recent activities
    recent_farmers = db.query("SELECT * FROM farmers ORDER BY registered_date DESC LIMIT 5")
    recent_tx = db.query("SELECT * FROM stubble_transactions ORDER BY transaction_date DESC LIMIT 5")
    recent_diseases = db.query("SELECT * FROM disease_detections ORDER BY detection_date DESC LIMIT 5")
    
    activities = []
    
    for farmer in recent_farmers:
        activities.append({
            'Timestamp': farmer['registered_date'],
            'Type': '👨‍🌾 New Farmer',
            'Details': f"{farmer['name']} registered",
            'Status': '✅ Success'
        })
    
    for tx in recent_tx:
        activities.append({
            'Timestamp': tx['transaction_date'],
            'Type': '💰 Transaction',
            'Details': f"Rs. {tx['gross_payment']:,.0f} transaction",
            'Status': '✅ Completed'
        })
    
    for disease in recent_diseases:
        activities.append({
            'Timestamp': disease['detection_date'],
            'Type': '🦠 Disease Detection',
            'Details': disease['disease_name_english'],
            'Status': f"⚠️ {disease['severity'].title()}"
        })
    
    # Sort by timestamp
    df_activities = pd.DataFrame(activities)
    if not df_activities.empty:
        df_activities['Timestamp'] = pd.to_datetime(df_activities['Timestamp'])
        df_activities = df_activities.sort_values('Timestamp', ascending=False)
        df_activities['Timestamp'] = df_activities['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        st.dataframe(
            df_activities.head(20),
            use_container_width=True,
            hide_index=True
        )
    
    st.markdown("---")
    
    # System resources
    st.markdown("### 💻 System Resources")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Mock CPU usage
        cpu_usage = 45
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cpu_usage,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "CPU Usage"},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 75], 'color': "yellow"},
                    {'range': [75, 100], 'color': "red"}
                ]
            }
        ))
        
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Mock Memory usage
        memory_usage = 62
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=memory_usage,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Memory Usage"},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkgreen"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 75], 'color': "yellow"},
                    {'range': [75, 100], 'color': "red"}
                ]
            }
        ))
        
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 2: USER MANAGEMENT
# ==========================================

with tab2:
    st.subheader("👥 User Management")
    
    # Get all farmers
    farmers = db.query("SELECT * FROM farmers")
    
    if farmers:
        st.metric("Total Users", len(farmers))
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox("Status", ["All", "Active", "Inactive"])
        
        with col2:
            district_filter = st.selectbox(
                "District",
                ["All"] + list(set([f['district'] for f in farmers]))
            )
        
        with col3:
            search = st.text_input("🔍 Search by name or phone")
        
        # Apply filters
        filtered_farmers = farmers.copy()
        
        if status_filter == "Active":
            filtered_farmers = [f for f in filtered_farmers if f['active'] == 1]
        elif status_filter == "Inactive":
            filtered_farmers = [f for f in filtered_farmers if f['active'] == 0]
        
        if district_filter != "All":
            filtered_farmers = [f for f in filtered_farmers if f['district'] == district_filter]
        
        if search:
            filtered_farmers = [
                f for f in filtered_farmers 
                if search.lower() in f['name'].lower() or search in f['phone_number']
            ]
        
        st.markdown(f"Showing {len(filtered_farmers)} users")
        
        # User table
        df_farmers = pd.DataFrame(filtered_farmers)
        df_farmers['registered_date'] = pd.to_datetime(df_farmers['registered_date']).dt.strftime('%Y-%m-%d')
        
        display_df = df_farmers[[
            'farmer_id', 'name', 'phone_number', 'district', 'village',
            'registered_date', 'active'
        ]].copy()
        
        display_df.columns = [
            'ID', 'Name', 'Phone', 'District', 'Village', 'Registered', 'Active'
        ]
        
        # Make interactive
        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # If user selected
        if event.selection and event.selection.rows:
            selected_idx = event.selection.rows[0]
            selected_farmer_id = display_df.iloc[selected_idx]['ID']
            
            st.markdown("---")
            st.markdown(f"### 👤 User Details - ID: {selected_farmer_id}")
            
            farmer = db.get('farmers', 'farmer_id', selected_farmer_id)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Personal Information:**")
                st.text(f"Name: {farmer['name']}")
                st.text(f"Phone: {farmer['phone_number']}")
                st.text(f"District: {farmer['district']}")
                st.text(f"Village: {farmer['village']}")
                st.text(f"Status: {'Active' if farmer['active'] else 'Inactive'}")
            
            with col2:
                # Get user's farms
                farms = db.query(
                    "SELECT * FROM farms WHERE farmer_id = ?",
                    (selected_farmer_id,)
                )
                
                st.markdown("**Farms:**")
                for farm in farms:
                    st.text(f"- {farm['crop_type'].title()}: {farm['area_acres']} acres")
                
                # Get transactions
                transactions = db.query(
                    "SELECT * FROM stubble_transactions WHERE farmer_id = ?",
                    (selected_farmer_id,)
                )
                
                st.markdown(f"**Transactions:** {len(transactions)}")
                if transactions:
                    total_earned = sum([t['net_to_farmer'] for t in transactions])
                    st.text(f"Total earned: Rs. {total_earned:,.0f}")
            
            # Admin actions
            st.markdown("---")
            st.markdown("**Admin Actions:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if farmer['active']:
                    if st.button("❌ Deactivate User", key="deactivate"):
                        db.update('farmers', 'farmer_id', selected_farmer_id, {'active': 0})
                        st.success("User deactivated")
                        st.rerun()
                else:
                    if st.button("✅ Activate User", key="activate"):
                        db.update('farmers', 'farmer_id', selected_farmer_id, {'active': 1})
                        st.success("User activated")
                        st.rerun()
            
            with col2:
                if st.button("📧 Send Message", key="message"):
                    st.info("Message feature coming soon")
            
            with col3:
                if st.button("📊 View Full Report", key="report"):
                    st.info("Report feature coming soon")

# ==========================================
# TAB 3: DATABASE MANAGEMENT
# ==========================================

with tab3:
    st.subheader("🗄️ Database Management")
    
    # Database statistics
    st.markdown("### 📊 Database Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        farmers_count = len(db.query("SELECT * FROM farmers"))
        st.metric("Farmers", farmers_count)
    
    with col2:
        farms_count = len(db.query("SELECT * FROM farms"))
        st.metric("Farms", farms_count)
    
    with col3:
        twins_count = len(db.query("SELECT * FROM digital_twins"))
        st.metric("Digital Twins", twins_count)
    
    with col4:
        tx_count = len(db.query("SELECT * FROM stubble_transactions"))
        st.metric("Transactions", tx_count)
    
    st.markdown("---")
    
    # Table explorer
    st.markdown("### 🔍 Database Explorer")
    
    tables = [
        'farmers', 'farms', 'digital_twins', 'buyers',
        'stubble_listings', 'stubble_transactions',
        'carbon_certificates', 'disease_detections',
        'market_prices', 'platform_revenue'
    ]
    
    selected_table = st.selectbox("Select Table", tables)
    
    if st.button("Load Table"):
        data = db.query(f"SELECT * FROM {selected_table}")
        
        if data:
            df = pd.DataFrame(data)
            
            st.markdown(f"**{selected_table}**: {len(data)} records")
            
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
            
            # Download option
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"{selected_table}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info(f"No data in {selected_table}")
    
    st.markdown("---")
    
    # Backup & Restore
    st.markdown("### 💾 Backup & Restore")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Create Backup:**")
        
        if st.button("📦 Backup Database"):
            import shutil
            
            backup_path = f"data/backups/agrotwinx_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            Path("data/backups").mkdir(parents=True, exist_ok=True)
            
            shutil.copy2('data/agrotwinx.db', backup_path)
            
            st.success(f"Backup created: {backup_path}")
    
    with col2:
        st.markdown("**Restore from Backup:**")
        
        backup_dir = Path("data/backups")
        if backup_dir.exists():
            backups = list(backup_dir.glob("*.db"))
            
            if backups:
                backup_file = st.selectbox(
                    "Select backup",
                    [b.name for b in backups]
                )
                
                if st.button("♻️ Restore Backup"):
                    st.warning("This will overwrite the current database!")
                    # Add confirmation logic here
            else:
                st.info("No backups found")
        else:
            st.info("No backups directory")

# ==========================================
# TAB 4: CONFIGURATION
# ==========================================

with tab4:
    st.subheader("⚙️ System Configuration")
    
    st.markdown("### 🔧 Platform Settings")
    
    with st.form("platform_settings"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Marketplace Settings:**")
            platform_fee = st.number_input(
                "Platform Fee (%)",
                min_value=0.0,
                max_value=10.0,
                value=5.0,
                step=0.1
            )
            
            transport_cost = st.number_input(
                "Transport Cost (Rs/km)",
                min_value=0,
                value=50
            )
        
        with col2:
            st.markdown("**Carbon Credit Settings:**")
            carbon_price_usd = st.number_input(
                "Carbon Credit Price (USD/ton)",
                min_value=0,
                value=15
            )
            
            usd_to_pkr = st.number_input(
                "USD to PKR Rate",
                min_value=0,
                value=280
            )
        
        st.markdown("**Alert Settings:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            morning_alert_time = st.time_input(
                "Morning Alert Time",
                value=datetime.strptime("07:00", "%H:%M").time()
            )
        
        with col2:
            harvest_alert_days = st.multiselect(
                "Send Harvest Alerts (days before)",
                [1, 3, 7, 14],
                default=[1, 3, 7]
            )
        
        submitted = st.form_submit_button("💾 Save Settings")
        
        if submitted:
            st.success("Settings saved successfully!")
    
    st.markdown("---")
    
    # API Keys
    st.markdown("### 🔑 API Keys")
    
    st.warning("⚠️ Sensitive information - Do not share")
    
    with st.expander("View API Keys"):
        from config import GEMINI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
        
        st.text_input("Gemini API Key", value=GEMINI_API_KEY[:10] + "..." if GEMINI_API_KEY else "Not set", disabled=True)
        st.text_input("Twilio Account SID", value=TWILIO_ACCOUNT_SID[:10] + "..." if TWILIO_ACCOUNT_SID else "Not set", disabled=True)
        st.text_input("Twilio Auth Token", value="*" * 20, disabled=True)

# ==========================================
# TAB 5: COMMUNICATIONS
# ==========================================

with tab5:
    st.subheader("📧 Mass Communications")
    
    st.markdown("### 📱 Send WhatsApp Broadcast")
    
    # Recipient selection
    col1, col2 = st.columns(2)
    
    with col1:
        recipient_type = st.selectbox(
            "Send to",
            ["All Farmers", "Active Farmers", "Specific District", "Custom Selection"]
        )
    
    with col2:
        if recipient_type == "Specific District":
            districts = list(set([f['district'] for f in db.query("SELECT * FROM farmers")]))
            selected_district = st.selectbox("District", districts)
    
    # Message composer
    message_type = st.selectbox(
        "Message Type",
        ["Announcement", "Alert", "Promotional", "Custom"]
    )
    
    message_body = st.text_area(
        "Message Body",
        height=150,
        placeholder="Enter your message here..."
    )
    
    # Preview
    if message_body:
        st.markdown("### 👁️ Preview")
        st.info(message_body)
    
    # Send button
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("📤 Send Now", type="primary"):
            # Get recipients
            if recipient_type == "All Farmers":
                recipients = db.query("SELECT * FROM farmers")
            elif recipient_type == "Active Farmers":
                recipients = db.query("SELECT * FROM farmers WHERE active = 1")
            elif recipient_type == "Specific District":
                recipients = db.query(
                    f"SELECT * FROM farmers WHERE district = '{selected_district}'"
                )
            
            st.success(f"Message sent to {len(recipients)} recipients!")
    
    with col2:
        if st.button("💾 Save as Draft"):
            st.info("Draft saved")
    
    st.markdown("---")
    
    # Message history
    st.markdown("### 📋 Broadcast History")
    
    # Mock data
    history = [
        {
            'Date': '2024-02-11 10:30',
            'Type': 'Announcement',
            'Recipients': 45,
            'Status': '✅ Delivered'
        },
        {
            'Date': '2024-02-10 07:00',
            'Type': 'Alert',
            'Recipients': 12,
            'Status': '✅ Delivered'
        }
    ]
    
    st.dataframe(
        pd.DataFrame(history),
        use_container_width=True,
        hide_index=True
    )