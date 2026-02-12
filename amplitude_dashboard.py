import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import json

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
    
    try:
        response = requests.get(url, auth=(api_key, secret_key))
        
        if response.status_code == 200:
            data = response.json()
            events_data = data.get('data', [])
            
            # Extract event names and create a mapping
            events = []
            for event in events_data:
                if isinstance(event, dict):
                    # Skip hidden and deleted events
                    if event.get('hidden', False) or event.get('deleted', False):
                        continue
                    
                    display_name = event.get('display', event.get('value', ''))
                    value_name = event.get('value', display_name)
                    
                    events.append({
                        'display': display_name,
                        'value': value_name,
                        'totals': event.get('totals', 0)
                    })
                else:
                    events.append({
                        'display': str(event),
                        'value': str(event),
                        'totals': 0
                    })
            
            # Sort by totals (most active events first)
            events.sort(key=lambda x: x.get('totals', 0), reverse=True)
            
            return events
        else:
            st.error(f"Error fetching events: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return []


def get_traffic(api_key, secret_key, start, end, event_value):
    """Get traffic data for specific event - tries multiple formats"""
    url = "https://amplitude.com/api/2/events/segmentation"
    
    # Try different event name formats
    event_attempts = []
    
    # Handle special Amplitude events first
    if '[Amplitude]' in event_value:
        if 'Any Active Event' in event_value:
            event_attempts.append('_active')
        elif 'Any Event' in event_value:
            event_attempts.append('_all')
        elif 'Page Viewed' in event_value or 'Page View' in event_value:
            # Try both with and without the [Amplitude] prefix
            event_attempts.append('Page Viewed')
            event_attempts.append('Page View')
    else:
        # For non-Amplitude events, try as-is first, then with ce: prefix
        event_attempts.append(event_value)
        event_attempts.append(f'ce:{event_value}')
    
    last_error = None
    
    # Try each format until one works
    for attempt in event_attempts:
        params = {
            "e": json.dumps({"event_type": attempt}),
            "start": start,
            "end": end,
            "m": "uniques"
        }
        
        try:
            response = requests.get(url, auth=(api_key, secret_key), params=params)
            
            if response.status_code == 200:
                data = response.json()
                # Check if we actually got data
                if data and 'data' in data and data['data'].get('series'):
                    st.success(f"✅ Found data using event name: `{attempt}`")
                    return data
            else:
                last_error = f"{response.status_code}: {response.text}"
        except Exception as e:
            last_error = str(e)
    
    # If all attempts failed, show what we tried
    st.error(f"Couldn't load data. Tried these event names:")
    for attempt in event_attempts:
        st.error(f"  • `{attempt}`")
    if last_error:
        st.error(f"Last error: {last_error}")
    
    return None


# Fetch all available events
with st.spinner("Loading your events from Amplitude..."):
    events = get_all_events(api_key, secret_key)

if not events:
    st.error("Couldn't fetch events. Check your API credentials.")
    st.stop()

# Create dropdown options with activity indicators
event_options = {}
display_names = []

for e in events:
    totals = e.get('totals', 0)
    if totals > 0:
        display_text = f"{e['display']} ({totals:,} events this week)"
    else:
        display_text = f"{e['display']} (no recent activity)"
    
    event_options[display_text] = e['value']
    display_names.append(display_text)

# Show event selector
st.subheader("Select Event to Analyze")
selected_display = st.selectbox("Pick an event:", display_names)
selected_event = event_options[selected_display]

# Show the actual event name being used
st.caption(f"Event value name: `{selected_event}`")

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
if st.button("🔄 Load Data") or 'last_event' not in st.session_state or st.session_state.last_event != selected_event:
    st.session_state.last_event = selected_event
    
    with st.spinner(f"Loading data for '{selected_display}'..."):
        data = get_traffic(api_key, secret_key, start_str, end_str, selected_event)
    
    if data and 'data' in data:
        dates = data['data'].get('xValues', [])
        values = data['data'].get('series', [[]])[0] if data['data'].get('series') else []
        
        if dates and values and len(dates) == len(values):
            # Metrics
            total = sum(values)
            avg_daily = total / len(values) if values else 0
            peak = max(values) if values else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📈 Total Visitors", f"{total:,}")
            col2.metric("📅 Daily Average", f"{avg_daily:.0f}")
            col3.metric("🔥 Peak Day", f"{peak:,}")
            
            # Chart
            st.subheader(f"Traffic for '{selected_display}'")
            
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
            
            # Data table
            st.subheader("Daily Breakdown")
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date', ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
        else:
            st.warning(f"No data found for '{selected_display}' in this time period.")
            st.info("This might mean:")
            st.info("• No users triggered this event during the selected period")
            st.info("• The event name doesn't match what's in Amplitude")
            st.info("• Try selecting a different event or time period")
    else:
        st.error(f"Couldn't fetch data for '{selected_display}'.")
        st.info("Check the event name or try a different event.")

st.markdown("---")
st.caption("💡 **Tip**: Events with higher counts are being tracked more frequently")
st.caption("🚀 **Best for website traffic**: Look for events like 'Page View', 'Session Start', or any custom pageview events")
st.caption("🔄 Click 'Load Data' button to refresh after changing selections")

with st.expander("ℹ️ Which event should I use?"):
    st.markdown("""
    **For tracking website traffic from promotions, look for:**
    - `Page View` or `Page Viewed` - Shows when users view pages
    - `Session Start` - Shows when users start a new session
    - `[Amplitude] Any Active Event` - Shows any user activity
    
    **Events with high counts** are being actively tracked and will give you the best data.
    
    **Events with "no recent activity"** might be old/unused events.
    """)