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

# Time period selector
period = st.selectbox("Time Period", ["Last 24 Hours", "Last 7 Days", "Last 30 Days"])

if period == "Last 24 Hours":
    days = 1
elif period == "Last 7 Days":
    days = 7
else:
    days = 30

end_date = datetime.now()
start_date = end_date - timedelta(days=days)
start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")


def get_traffic(api_key, secret_key, start, end):
    """Get traffic data from Amplitude"""
    url = "https://amplitude.com/api/2/events/segmentation"
    params = {
        "e": {"event_type": "Page Viewed"},
        "start": start,
        "end": end
    }
    
    response = requests.get(url, auth=(api_key, secret_key), params=params)
    
    if response.status_code == 200:
        return response.json()
    return None


# Fetch data
with st.spinner("Loading traffic data..."):
    data = get_traffic(api_key, secret_key, start_str, end_str)

if data and 'data' in data:
    # Get the traffic numbers
    dates = data['data'].get('xValues', [])
    values = data['data'].get('series', [[]])[0]
    
    if dates and values:
        # Total traffic
        total = sum(values)
        avg_daily = total / len(values) if values else 0
        
        # Show metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("📈 Total Traffic", f"{total:,}")
        col2.metric("📅 Daily Average", f"{avg_daily:.0f}")
        col3.metric("🔥 Peak Day", f"{max(values):,}")
        
        # Traffic chart
        st.subheader("Traffic Trend")
        
        df = pd.DataFrame({'Date': dates, 'Visitors': values})
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['Date'], 
            y=df['Visitors'],
            mode='lines+markers',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.2)'
        ))
        
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Visitors",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show the data table
        st.subheader("Daily Breakdown")
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date', ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    else:
        st.warning("No traffic data found. Check your Amplitude event name.")
else:
    st.error("Couldn't fetch data. Check your Amplitude setup and make sure you're tracking 'Page Viewed' events.")

st.markdown("---")
st.caption("💡 Post your promotion and refresh to see if traffic spikes")