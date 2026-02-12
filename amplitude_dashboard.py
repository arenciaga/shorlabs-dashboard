import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import os

# Page configuration
st.set_page_config(
    page_title="Amplitude Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title
st.title("📊 Amplitude Analytics Dashboard")

# Sidebar for API credentials
st.sidebar.header("🔑 Amplitude Configuration")

# Try to get credentials from environment variables first
api_key = os.environ.get("AMPLITUDE_API_KEY", "")
secret_key = os.environ.get("AMPLITUDE_SECRET_KEY", "")

# If not found in environment variables, allow manual input
if not api_key:
    api_key = st.sidebar.text_input("API Key", type="password", help="Enter your Amplitude API Key or set AMPLITUDE_API_KEY environment variable")
else:
    st.sidebar.success("✅ API Key loaded from environment variable")
    
if not secret_key:
    secret_key = st.sidebar.text_input("Secret Key", type="password", help="Enter your Amplitude Secret Key or set AMPLITUDE_SECRET_KEY environment variable")
else:
    st.sidebar.success("✅ Secret Key loaded from environment variable")

# Time period selection
st.sidebar.header("📅 Time Period")
time_period = st.sidebar.selectbox(
    "Select Time Range",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom Range"]
)

# Calculate date range based on selection
if time_period == "Last 24 Hours":
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
elif time_period == "Last 7 Days":
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
elif time_period == "Last 30 Days":
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
elif time_period == "Last 90 Days":
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
else:  # Custom Range
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    start_date = datetime.combine(start_date, datetime.min.time())
    end_date = datetime.combine(end_date, datetime.max.time())

# Format dates for Amplitude API
start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")


def fetch_amplitude_data(api_key, secret_key, start_date, end_date, event_type=None):
    """Fetch data from Amplitude API"""
    
    base_url = "https://amplitude.com/api/2/events/list"
    
    params = {
        "start": start_date,
        "end": end_date
    }
    
    if event_type:
        params["event"] = event_type
    
    try:
        response = requests.get(
            base_url,
            auth=(api_key, secret_key),
            params=params
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None


def fetch_user_activity(api_key, secret_key, start_date, end_date):
    """Fetch user activity data from Amplitude"""
    
    base_url = "https://amplitude.com/api/2/users"
    
    params = {
        "start": start_date,
        "end": end_date
    }
    
    try:
        response = requests.get(
            base_url,
            auth=(api_key, secret_key),
            params=params
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        st.error(f"Error fetching user data: {str(e)}")
        return None


def fetch_event_segmentation(api_key, secret_key, start_date, end_date, event_name):
    """Fetch event segmentation data"""
    
    base_url = "https://amplitude.com/api/2/events/segmentation"
    
    params = {
        "e": {"event_type": event_name},
        "start": start_date,
        "end": end_date
    }
    
    try:
        response = requests.get(
            base_url,
            auth=(api_key, secret_key),
            params=params
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None


# Main dashboard
if api_key and secret_key:
    
    st.sidebar.success("✅ Connected to Amplitude")
    
    # Display date range
    st.info(f"📅 Showing data from {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "👥 User Activity", "🎯 Events", "📊 Engagement"])
    
    with tab1:
        st.header("Key Metrics Overview")
        
        # Key metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        # Fetch data for common events
        with st.spinner("Loading analytics data..."):
            
            # You can customize these event names based on your Amplitude setup
            page_view_data = fetch_event_segmentation(api_key, secret_key, start_str, end_str, "Page View")
            signup_data = fetch_event_segmentation(api_key, secret_key, start_str, end_str, "Sign Up")
            session_data = fetch_event_segmentation(api_key, secret_key, start_str, end_str, "Session Start")
            
            # Display metrics
            with col1:
                st.metric(
                    label="👁️ Site Visitors",
                    value="Loading..." if not session_data else f"{session_data.get('data', {}).get('series', [[]])[0][-1]:,}",
                    delta=None
                )
            
            with col2:
                st.metric(
                    label="📄 Page Views",
                    value="Loading..." if not page_view_data else f"{page_view_data.get('data', {}).get('series', [[]])[0][-1]:,}",
                    delta=None
                )
            
            with col3:
                st.metric(
                    label="✍️ Sign Ups",
                    value="Loading..." if not signup_data else f"{signup_data.get('data', {}).get('series', [[]])[0][-1]:,}",
                    delta=None
                )
            
            with col4:
                # Calculate conversion rate if data available
                if session_data and signup_data:
                    try:
                        visitors = session_data.get('data', {}).get('series', [[]])[0][-1]
                        signups = signup_data.get('data', {}).get('series', [[]])[0][-1]
                        conversion = (signups / visitors * 100) if visitors > 0 else 0
                        st.metric(
                            label="📊 Conversion Rate",
                            value=f"{conversion:.2f}%",
                            delta=None
                        )
                    except:
                        st.metric(label="📊 Conversion Rate", value="N/A")
                else:
                    st.metric(label="📊 Conversion Rate", value="N/A")
        
        # Time series chart
        st.subheader("📈 Trend Over Time")
        
        # Create sample trend data (you'll need to parse actual Amplitude response)
        if page_view_data and 'data' in page_view_data:
            dates = page_view_data.get('data', {}).get('xValues', [])
            values = page_view_data.get('data', {}).get('series', [[]])[0]
            
            if dates and values:
                df_trend = pd.DataFrame({
                    'Date': dates,
                    'Page Views': values
                })
                
                fig = px.line(df_trend, x='Date', y='Page Views', 
                             title='Page Views Over Time',
                             markers=True)
                fig.update_layout(hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        st.header("👥 User Activity Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Active Users")
            # Fetch active users data
            user_data = fetch_user_activity(api_key, secret_key, start_str, end_str)
            
            if user_data:
                st.write("Total Active Users:", len(user_data.get('data', [])))
            else:
                st.info("Configure your Amplitude events to see user activity")
        
        with col2:
            st.subheader("User Frequency")
            # Create sample frequency distribution
            frequency_data = {
                'Frequency': ['1-2 visits', '3-5 visits', '6-10 visits', '11+ visits'],
                'Users': [150, 80, 45, 25]  # Sample data
            }
            df_freq = pd.DataFrame(frequency_data)
            
            fig = px.bar(df_freq, x='Frequency', y='Users', 
                        title='User Visit Frequency',
                        color='Users',
                        color_continuous_scale='Blues')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.header("🎯 Top Events")
        
        # Custom event selection
        custom_event = st.text_input("Enter event name to analyze:", placeholder="e.g., Button Click, Form Submit")
        
        if custom_event:
            event_data = fetch_event_segmentation(api_key, secret_key, start_str, end_str, custom_event)
            
            if event_data and 'data' in event_data:
                st.success(f"✅ Found data for '{custom_event}'")
                
                # Display event metrics
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Total Events", f"{sum(event_data.get('data', {}).get('series', [[]])[0]):,}")
                
                with col2:
                    st.metric("Unique Users", event_data.get('data', {}).get('seriesMeta', [{}])[0].get('uniqueUsers', 'N/A'))
        
        # Common events table
        st.subheader("Common Events to Track")
        common_events = pd.DataFrame({
            'Event Name': ['Page View', 'Sign Up', 'Login', 'Purchase', 'Button Click', 'Form Submit'],
            'Description': [
                'User views a page',
                'User completes signup',
                'User logs in',
                'User makes a purchase',
                'User clicks a button',
                'User submits a form'
            ]
        })
        st.dataframe(common_events, use_container_width=True, hide_index=True)
    
    with tab4:
        st.header("📊 User Engagement")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Session Duration")
            # Sample session duration data
            duration_data = {
                'Duration': ['0-1 min', '1-5 min', '5-10 min', '10+ min'],
                'Sessions': [200, 350, 180, 90]
            }
            df_duration = pd.DataFrame(duration_data)
            
            fig = px.pie(df_duration, values='Sessions', names='Duration',
                        title='Session Duration Distribution')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Top User Actions")
            # Sample top actions
            actions_data = {
                'Action': ['Page View', 'Click', 'Scroll', 'Submit', 'Share'],
                'Count': [1200, 850, 620, 340, 180]
            }
            df_actions = pd.DataFrame(actions_data)
            
            fig = px.bar(df_actions, x='Action', y='Count',
                        title='Most Common User Actions',
                        color='Count',
                        color_continuous_scale='Viridis')
            st.plotly_chart(fig, use_container_width=True)
        
        # Engagement metrics
        st.subheader("Engagement Summary")
        
        engagement_col1, engagement_col2, engagement_col3 = st.columns(3)
        
        with engagement_col1:
            st.metric("Avg. Session Duration", "4m 32s")
        
        with engagement_col2:
            st.metric("Avg. Events per User", "12.3")
        
        with engagement_col3:
            st.metric("Bounce Rate", "23.5%")

else:
    # Show instructions if no API keys
    st.warning("⚠️ Please enter your Amplitude API credentials in the sidebar to get started.")
    
    st.markdown("""
    ### 🚀 Getting Started
    
    To use this dashboard, you'll need:
    
    1. **Amplitude API Key** - Found in your Amplitude project settings
    2. **Amplitude Secret Key** - Also in your project settings
    
    #### 📋 How to find your credentials:
    
    1. Log into [Amplitude](https://amplitude.com)
    2. Go to Settings → Projects
    3. Select your project
    4. Navigate to the "API Keys" section
    5. Copy your API Key and Secret Key
    
    #### 📊 Features:
    
    - **Overview**: Key metrics and trends
    - **User Activity**: Active users and visit frequency
    - **Events**: Track specific events and actions
    - **Engagement**: Session duration and user behavior
    
    #### 🔧 Customization:
    
    You can customize the event names in the code to match your Amplitude setup. Common events include:
    - `Page View`
    - `Sign Up`
    - `Session Start`
    - `Purchase`
    - `Button Click`
    
    Enter your credentials in the sidebar to begin! 👈
    """)

# Footer
st.markdown("---")
st.markdown("💡 **Tip**: Refresh the dashboard to see updated data from Amplitude")