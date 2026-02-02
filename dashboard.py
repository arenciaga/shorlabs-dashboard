import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Attr
import pandas as pd
import requests
from functools import lru_cache

# Load environment variables from a local .env file (useful when running locally).
# On Streamlit Cloud, values should come from st.secrets instead.
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Shorlabs Projects",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 Shorlabs Projects Dashboard")

CLERK_API_URL = os.getenv("CLERK_API_URL", "https://api.clerk.com/v1")


@lru_cache(maxsize=512)
def fetch_clerk_user(user_id: str) -> dict:
    """Fetch a user's profile from Clerk by user_id (cached)."""
    if not user_id or user_id in ("N/A", ""):
        return {}

    # Prefer Streamlit secrets, fall back to env/.env
    clerk_secret = None
    try:
        clerk_secret = st.secrets["CLERK_SECRET_KEY"]
    except Exception:
        clerk_secret = os.getenv("CLERK_SECRET_KEY")

    if not clerk_secret:
        # If Clerk isn't configured, just skip enrichment
        return {}

    try:
        resp = requests.get(
            f"{CLERK_API_URL}/users/{user_id}",
            headers={"Authorization": f"Bearer {clerk_secret}"},
            timeout=5,
        )
        if resp.status_code != 200:
            return {}

        data = resp.json()

        # Subscription / billing often lives in public_metadata or private_metadata.
        # You should set these fields in Clerk (e.g. via dashboard or webhook):
        # public_metadata.subscription_plan, public_metadata.subscription_status, public_metadata.billing_status
        public_meta = data.get("public_metadata", {}) or {}
        subscription_plan = public_meta.get("subscription_plan")
        subscription_status = public_meta.get("subscription_status")
        billing_status = public_meta.get("billing_status")

        # Try to determine the primary email from Clerk's email_addresses list
        email = None
        try:
            primary_email_id = data.get("primary_email_address_id")
            email_addresses = data.get("email_addresses", []) or []
            if primary_email_id:
                for e in email_addresses:
                    if e.get("id") == primary_email_id:
                        email = e.get("email_address")
                        break
            if not email and email_addresses:
                # Fallback: first email in the list
                email = email_addresses[0].get("email_address")
        except Exception:
            email = None

        return {
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": email,
            "subscription_plan": subscription_plan,
            "subscription_status": subscription_status,
            "billing_status": billing_status,
        }
    except Exception:
        # Fail silently; Dynamo data will still render
        return {}

@st.cache_data(ttl=60)
def load_data():
    """Fetches project data from DynamoDB."""
    try:
        # Prefer Streamlit secrets (when they exist, e.g. on Streamlit Cloud).
        # If no secrets file is found (your local case), fall back to .env/env vars.
        try:
            region = st.secrets["AWS_REGION"]
            access_key = st.secrets["AWS_ACCESS_KEY_ID"]
            secret_key = st.secrets["AWS_SECRET_ACCESS_KEY"]
        except Exception:
            region = os.getenv("AWS_REGION", "us-east-1")
            access_key = os.getenv("AWS_ACCESS_KEY_ID")
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        dynamodb = boto3.resource(
            "dynamodb",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        table = dynamodb.Table('shorlabs-projects')
        
        # Scan table for projects
        response = table.scan(
            FilterExpression=Attr('SK').begins_with('PROJECT#')
        )
        items = response.get('Items', [])
        
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=Attr('SK').begins_with('PROJECT#'),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
            
        return items
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return []

def process_data(items):
    """Processes raw DynamoDB items into a DataFrame."""
    if not items:
        return pd.DataFrame()
        
    data = []
    for item in items:
        user_id = item.get("user_id", "N/A")

        # Enrich with Clerk profile data
        clerk_info = fetch_clerk_user(user_id)

        # Determine the project URL
        # Logic: custom_url > function_url > N/A
        url = item.get('custom_url')
        if not url:
            url = item.get('function_url', 'N/A')
            
        data.append(
            {
                "User ID": user_id,
                "First Name": clerk_info.get("first_name", ""),
                "Last Name": clerk_info.get("last_name", ""),
                "Email": clerk_info.get("email", ""),
                "Subscription Plan": clerk_info.get("subscription_plan", ""),
                "Subscription Status": clerk_info.get("subscription_status", ""),
                "Billing Status": clerk_info.get("billing_status", ""),
                "Project ID": item.get("project_id", "N/A"),
                "Date Deployed": item.get("created_at", "N/A"),
                "Project URL": url,
                # Extra fields that might be useful in a detail view
                "Name": item.get("name", ""),
                "Status": item.get("status", ""),
                "Region": item.get(
                    "AWS_REGION", "us-east-1"
                ),  # Not directly in item usually, but good to have
                "Memory": item.get("memory", ""),
                "Timeout": item.get("timeout", ""),
            }
        )
    
    return pd.DataFrame(data)

# Main App Logic
with st.spinner('Loading projects...'):
    items = load_data()
    df = process_data(items)

if df.empty:
    st.warning("No projects found or unable to connect to database.")
else:
    # Key Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Projects", len(df))
    col2.metric("Unique Users", df['User ID'].nunique())
    
    st.subheader("Project List")
    
    # Configure the dataframe for better display (show Clerk user info too)
    main_columns = [
        "User ID",
        "First Name",
        "Last Name",
        "Email",
        "Subscription Plan",
        "Subscription Status",
        "Billing Status",
        "Project ID",
        "Date Deployed",
        "Project URL",
    ]

    st.dataframe(
        df[main_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Project URL": st.column_config.LinkColumn("Project URL"),
            "Date Deployed": st.column_config.DatetimeColumn(
                "Date Deployed", format="D MMM YYYY, HH:mm:ss"
            ),
        },
    )
    
    # Optional: Detailed View expander
    with st.expander("View Raw Data"):
        st.dataframe(df)

# Footer
st.markdown("---")
st.caption("Data pulled from DynamoDB 'shorlabs-projects' table.")
