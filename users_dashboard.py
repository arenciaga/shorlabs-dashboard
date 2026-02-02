import streamlit as st
import requests
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

st.set_page_config(page_title="Users Dashboard", layout="wide")

st.title("Users Dashboard")

if not CLERK_SECRET_KEY:
    st.error("CLERK_SECRET_KEY not found in environment variables.")
else:
    # Fetch users from Clerk
    # Setting limit to 100 for now. You might want to implement pagination for production.
    url = "https://api.clerk.com/v1/users?limit=100"
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    with st.spinner("Fetching users from Clerk..."):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            users_data = response.json()
            
            # Identify if the response is a list or a paginated object
            if isinstance(users_data, list):
                users_list = users_data
            elif isinstance(users_data, dict) and 'response' in users_data: # Sometimes keys vary
                users_list = users_data.get('response', [])
            else:
                 users_list = users_data # Fallback, assume it iterates or pandas handles it
            
            parsed_users = []
            for user in users_list:
                # Clerk timestamps are in milliseconds
                created_at_ms = user.get('created_at')
                if created_at_ms:
                    sign_up_date = datetime.fromtimestamp(created_at_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    sign_up_date = "N/A"
                
                parsed_users.append({
                    "User ID": user.get('id'),
                    "First Name": user.get('first_name'),
                    "Last Name": user.get('last_name'),
                    "Sign Up Date": sign_up_date
                })
                
            if parsed_users:
                df = pd.DataFrame(parsed_users)
                st.dataframe(df, use_container_width=True)
                st.success(f"Successfully loaded {len(df)} users.")
            else:
                st.info("No users found.")
                
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching users: {e}")
