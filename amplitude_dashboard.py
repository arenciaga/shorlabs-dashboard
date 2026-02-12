import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Traffic Dashboard", page_icon="📊", layout="wide")

# Get API credentials
try:
    api_key = st.secrets["AMPLITUDE_API_KEY"]
    secret_key = st.secrets["AMPLITUDE_SECRET_KEY"]
except:
    st.error("Add your Amplitude keys to .streamlit/secrets.toml")
    st.stop()

st.title("📊 Website Traffic Dashboard")


def get_all_events(api_key, secret_key):
    """Fetch all events from Amplitude"""
    url = "https://amplitude.com/api/2/events/list"
    
    response = requests.get(url, auth=(api_key, secret_key))
    
    if response.status_code == 200:
        data = response.json()
        return data.get('data', [])
    return []


def get_traffic(api_key, secret_key, start, end, event_name):
    """Get traffic data for specific event"""
    url = "https://amplitude.com/api/2/events/segmentation"
    params = {
        "e": {"event_type": event_name},
        "start": start,
        "end": end
    }
    
    response = requests.get(url, auth=(api_key, secret_key), params=params)
    
    if response.status_code == 200:
        return response.json()
    return None


# Fetch all available events
with st.spinner("Loading your events from Amplitude..."):
    events = get_all_events(api_key, secret_key)

if not events:
    st.error("Couldn't fetch events. Check your API credentials.")
    st.stop()

# Show event selector
st.subheader("Select Event to Analyze")
event_names = [event.get('name', event) if isinstance(event, dict) else event for event in events]
selected_event = st.selectbox("Pick an event:", event_names)

# Time period selector
period = st.selectbox("Time Period", ["Last 7 Days", "Last 30 Days", "Last 90 Days"])

if period == "Last 7 Days":
    days = 7
elif period == "Last 30 Days":
    days = 30
else:
    days = 90

end_date = datetime.now()
start_date = end_date - timedelta(days=days)
start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")

# Fetch data for selected event
if selected_event:
    with st.spinner(f"Loading data for '{selected_event}'..."):
        data = get_traffic(api_key, secret_key, start_str, end_str, selected_event)
    
    if data and 'data' in data:
        dates = data['data'].get('xValues', [])
        values = data['data'].get('series', [[]])[0]
        
        if dates and values:
            # Metrics
            total = sum(values)
            avg_daily = total / len(values) if values else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📈 Total Events", f"{total:,}")
            col2.metric("📅 Daily Average", f"{avg_daily:.0f}")
            col3.metric("🔥 Peak Day", f"{max(values):,}")
            
            # Chart
            st.subheader(f"Traffic for '{selected_event}'")
            
            df = pd.DataFrame({'Date': dates, 'Count': values})
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df['Date'], 
                y=df['Count'],
                mode='lines+markers',
                line=dict(color='#1f77b4', width=3),
                marker=dict(size=8),
                fill='tozeroy',
                fillcolor='rgba(31, 119, 180, 0.2)'
            ))
            
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Events",
                hovermode='x unified',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Data table
            st.subheader("Daily Breakdown")
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date', ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No data found for '{selected_event}' in this time period.")
    else:
        st.error(f"Couldn't fetch data for '{selected_event}'.")

st.markdown("---")
st.caption("💡 Select different events to see which ones are getting traffic")