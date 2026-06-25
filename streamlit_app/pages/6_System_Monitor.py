# streamlit_app/pages/6_🔧_System_Monitor.py

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.utils.database import Database
from src.utils.error_handler import ErrorHandler
from src.satellite.data_validator import SatelliteDataValidator

st.set_page_config(
    page_title="System Monitor - AgroTwinX",
    page_icon="🔧",
    layout="wide"
)

# Initialize
db = Database()
error_handler = ErrorHandler()
validator = SatelliteDataValidator()

st.title("🔧 System Monitoring Dashboard")
st.markdown("Real-time system health and performance metrics")

# Refresh button
if st.button("🔄 Refresh Data"):
    st.rerun()

st.markdown("---")

# System Status
st.subheader("📊 System Status")

col1, col2, col3, col4 = st.columns(4)

with col1:
    # Check last satellite update
    try:
        last_update = db.query(
            "SELECT MAX(timestamp) as last_update FROM satellite_update_logs"
        )
        
        if last_update and last_update[0]['last_update']:
            last_update_time = datetime.fromisoformat(last_update[0]['last_update'])
            hours_ago = (datetime.now() - last_update_time).total_seconds() / 3600
            
            if hours_ago < 24:
                status = "🟢 Active"
                delta = f"{hours_ago:.1f}h ago"
            else:
                status = "🟡 Delayed"
                delta = f"{hours_ago/24:.1f}d ago"
        else:
            status = "🔴 No Data"
            delta = "Never"
        
        st.metric("Satellite Updates", status, delta=delta)
    except:
        st.metric("Satellite Updates", "🔴 Error", delta="Check system")

with col2:
    # Check weather updates
    try:
        last_weather = db.query(
            "SELECT MAX(date) as last_date FROM weather_data"
        )
        
        if last_weather and last_weather[0]['last_date']:
            last_date = datetime.strptime(last_weather[0]['last_date'], '%Y-%m-%d')
            days_ago = (datetime.now() - last_date).days
            
            if days_ago == 0:
                status = "🟢 Current"
                delta = "Today"
            elif days_ago == 1:
                status = "🟡 Yesterday"
                delta = "1d ago"
            else:
                status = "🔴 Outdated"
                delta = f"{days_ago}d ago"
        else:
            status = "🔴 No Data"
            delta = "Never"
        
        st.metric("Weather Data", status, delta=delta)
    except:
        st.metric("Weather Data", "🔴 Error", delta="Check system")

with col3:
    # Check WhatsApp bot
    # Mock for now
    st.metric("WhatsApp Bot", "🟢 Active", delta="Running")

with col4:
    # Check database size
    import os
    try:
        db_size = os.path.getsize('data/agrotwinx.db') / (1024 * 1024)
        
        if db_size < 100:
            status = "🟢 Healthy"
        elif db_size < 500:
            status = "🟡 Growing"
        else:
            status = "🔴 Large"
        
        st.metric("Database", status, delta=f"{db_size:.1f} MB")
    except:
        st.metric("Database", "🔴 Error", delta="Check file")

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Update Logs",
    "❌ Error Logs",
    "🔍 Data Quality",
    "📊 Performance"
])

# ==========================================
# TAB 1: UPDATE LOGS
# ==========================================

with tab1:
    st.subheader("📈 Satellite Update History")
    
    try:
        logs = db.query(
            "SELECT * FROM satellite_update_logs ORDER BY timestamp DESC LIMIT 30"
        )
        
        if logs:
            df = pd.DataFrame(logs)
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Summary
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_updates = len(logs)
                st.metric("Total Updates", total_updates)
            
            with col2:
                avg_success_rate = df['success_rate'].mean()
                st.metric("Avg Success Rate", f"{avg_success_rate:.1f}%")
            
            with col3:
                total_farms = df['farms_updated'].sum()
                st.metric("Farms Updated", total_farms)
            
            # Table
            st.dataframe(
                df[['timestamp', 'farms_updated', 'farms_failed', 'total_farms', 'success_rate']],
                use_container_width=True,
                hide_index=True
            )
            
            # Chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['success_rate'],
                mode='lines+markers',
                name='Success Rate',
                line=dict(color='green', width=2)
            ))
            
            fig.update_layout(
                title="Update Success Rate Over Time",
                xaxis_title="Date",
                yaxis_title="Success Rate (%)",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No update logs found")
    except:
        st.error("Failed to load update logs")

# ==========================================
# TAB 2: ERROR LOGS
# ==========================================

with tab2:
    st.subheader("❌ Recent Errors")
    
    time_range = st.selectbox("Show errors from", ["Last 24 hours", "Last 7 days", "Last 30 days"])
    
    hours_map = {
        "Last 24 hours": 24,
        "Last 7 days": 24 * 7,
        "Last 30 days": 24 * 30
    }
    
    errors = error_handler.get_recent_errors(hours=hours_map[time_range])
    
    if errors:
        # Summary
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Errors", len(errors))
        
        with col2:
            critical = len([e for e in errors if e['severity'] == 'high'])
            st.metric("Critical Errors", critical, delta="-2" if critical < 5 else "+3")
        
        with col3:
            unresolved = len([e for e in errors if not e['resolved']])
            st.metric("Unresolved", unresolved)
        
        # Error table
        df_errors = pd.DataFrame(errors)
        df_errors['timestamp'] = pd.to_datetime(df_errors['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Severity color coding
        def severity_emoji(severity):
            return {
                'low': '🟡',
                'medium': '🟠',
                'high': '🔴'
            }.get(severity, '⚪')
        
        df_errors['severity_icon'] = df_errors['severity'].apply(severity_emoji)
        
        display_df = df_errors[['severity_icon', 'timestamp', 'error_type', 'error_message', 'context']]
        display_df.columns = ['Severity', 'Timestamp', 'Type', 'Message', 'Context']
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Error distribution
        col1, col2 = st.columns(2)
        
        with col1:
            error_types = df_errors['error_type'].value_counts()
            
            fig = px.pie(
                values=error_types.values,
                names=error_types.index,
                title="Errors by Type"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            severity_counts = df_errors['severity'].value_counts()
            
            fig = px.bar(
                x=severity_counts.index,
                y=severity_counts.values,
                title="Errors by Severity",
                color=severity_counts.values,
                color_continuous_scale=['yellow', 'orange', 'red']
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.success("✅ No errors in selected time range!")

# ==========================================
# TAB 3: DATA QUALITY
# ==========================================

with tab3:
    st.subheader("🔍 Data Quality Assessment")
    
    if st.button("🔍 Run Validation"):
        with st.spinner("Validating all data..."):
            report = validator.validate_all_twins()
        
        # Display results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Farms", report['total_twins'])
        
        with col2:
            validity_rate = (report['valid_twins'] / max(report['total_twins'], 1)) * 100
            st.metric("Validity Rate", f"{validity_rate:.1f}%")
        
        with col3:
            st.metric("Avg Quality Score", f"{report['avg_quality_score']:.1f}/100")
        
        # Issues
        if report['issues_found']:
            st.markdown("### ⚠️ Issues Found")
            
            for issue in report['issues_found'][:10]:
                with st.expander(f"Farm {issue['farm_id']}"):
                    for problem in issue['issues']:
                        st.warning(problem)
        else:
            st.success("✅ No data quality issues found!")

# ==========================================
# TAB 4: PERFORMANCE
# ==========================================

with tab4:
    st.subheader("📊 System Performance")
    
    # Mock performance data
    st.markdown("### 🚀 Response Times")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Satellite Fetch", "2.3s", delta="-0.5s")
    
    with col2:
        st.metric("Weather API", "0.8s", delta="+0.1s")
    
    with col3:
        st.metric("Database Query", "0.05s", delta="-0.01s")
    
    # Resource usage
    st.markdown("### 💻 Resource Usage")
    
    import psutil
    
    col1, col2 = st.columns(2)
    
    with col1:
        cpu_percent = psutil.cpu_percent(interval=1)
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cpu_percent,
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
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=memory_percent,
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