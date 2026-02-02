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
    # Setting limit to 500 to capture more users. Implement pagination loop for full coverage > 500.
    url = "https://api.clerk.com/v1/users?limit=500"
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
            elif isinstance(users_data, dict) and 'response' in users_data:
                users_list = users_data.get('response', [])
            elif isinstance(users_data, dict) and 'data' in users_data: # standard paginated response
                users_list = users_data.get('data', [])
            else:
                 users_list = users_data # Fallback
            
            parsed_users = []
            for user in users_list:
                # Clerk timestamps are in milliseconds
                created_at_ms = user.get('created_at')
                if created_at_ms:
                    sign_up_date = datetime.fromtimestamp(created_at_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    sign_up_date = "N/A"
                
                # Extract Email
                email = "N/A"
                email_addresses = user.get('email_addresses', [])
                primary_id = user.get('primary_email_address_id')
                
                if email_addresses:
                    # Try to find primary email
                    if primary_id:
                        for email_obj in email_addresses:
                            if email_obj.get('id') == primary_id:
                                email = email_obj.get('email_address')
                                break
                    
                    # Fallback to first email if primary not found or no primary_id
                    if email == "N/A":
                        email = email_addresses[0].get('email_address')

                parsed_users.append({
                    "User ID": user.get('id'),
                    "First Name": user.get('first_name'),
                    "Last Name": user.get('last_name'),
                    "Email": email,
                    "Sign Up Date": sign_up_date
                })
                
            if parsed_users:
                df = pd.DataFrame(parsed_users)
                
                # Top Level Metrics
                st.metric(label="Total Unique Users", value=len(df))

                st.dataframe(df, use_container_width=True)
                
                # CSV Export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name='users_export.csv',
                    mime='text/csv',
                )
                
                st.success(f"Successfully loaded {len(df)} users.")
            else:
                st.info("No users found.")
                
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching users: {e}")
