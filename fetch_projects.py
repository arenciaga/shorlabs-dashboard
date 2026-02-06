import streamlit as st
import boto3
import pandas as pd
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key, Attr

# Load environment variables
load_dotenv()


def format_date(iso_date_str):
    """Format ISO date string to a more readable format"""
    if not iso_date_str or iso_date_str == 'N/A':
        return 'N/A'
    try:
        # Parse ISO format like "2026-02-04T22:18:11.905013"
        dt = datetime.fromisoformat(iso_date_str.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y %I:%M %p')  # e.g., "Feb 04, 2026 10:18 PM"
    except (ValueError, AttributeError):
        return iso_date_str  # Return original if parsing fails

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

st.set_page_config(page_title="Projects Dashboard", layout="wide")

st.title("Projects Dashboard")


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_clerk_organizations():
    """Fetch all organizations from Clerk and return a dict mapping org_id -> org_info"""
    if not CLERK_SECRET_KEY:
        st.warning("CLERK_SECRET_KEY not found. Organization names will not be available.")
        return {}
    
    orgs_map = {}
    url = "https://api.clerk.com/v1/organizations?limit=500"
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        orgs_data = response.json()
        
        # Handle different response formats
        if isinstance(orgs_data, list):
            orgs_list = orgs_data
        elif isinstance(orgs_data, dict) and 'data' in orgs_data:
            orgs_list = orgs_data.get('data', [])
        else:
            orgs_list = []
        
        for org in orgs_list:
            org_id = org.get('id')
            if org_id:
                orgs_map[org_id] = {
                    'name': org.get('name', 'N/A'),
                    'created_by': org.get('created_by'),
                }
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching organizations from Clerk: {e}")
    
    return orgs_map


def fetch_org_admin_email(org_id):
    """Fetch the admin member of an organization and return their email"""
    if not CLERK_SECRET_KEY:
        return "N/A"
    
    url = f"https://api.clerk.com/v1/organizations/{org_id}/memberships?limit=100"
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        memberships_data = response.json()
        
        # Handle different response formats
        if isinstance(memberships_data, list):
            memberships = memberships_data
        elif isinstance(memberships_data, dict) and 'data' in memberships_data:
            memberships = memberships_data.get('data', [])
        else:
            memberships = []
        
        # Find admin member
        for membership in memberships:
            role = membership.get('role', '')
            if role == 'org:admin' or role == 'admin':
                # Get user info from public_user_data
                public_user_data = membership.get('public_user_data', {})
                # Try identifier first (usually email), then other fields
                email = public_user_data.get('identifier')
                if not email:
                    # Fallback: fetch user details
                    user_id = public_user_data.get('user_id')
                    if user_id:
                        email = fetch_user_email(user_id)
                return email if email else "N/A"
        
        # If no admin found, return first member's email
        if memberships:
            public_user_data = memberships[0].get('public_user_data', {})
            email = public_user_data.get('identifier')
            return email if email else "N/A"
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching org memberships for {org_id}: {e}")
    
    return "N/A"


def fetch_user_email(user_id):
    """Fetch a user's email by their ID"""
    if not CLERK_SECRET_KEY:
        return None
    
    url = f"https://api.clerk.com/v1/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        user = response.json()
        
        email_addresses = user.get('email_addresses', [])
        primary_id = user.get('primary_email_address_id')
        
        if email_addresses:
            if primary_id:
                for email_obj in email_addresses:
                    if email_obj.get('id') == primary_id:
                        return email_obj.get('email_address')
            return email_addresses[0].get('email_address')
    except requests.exceptions.RequestException as e:
        pass  # Silently fail for individual user fetches
    
    return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_projects_from_dynamodb():
    """Fetch projects from DynamoDB"""
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    table_name = 'shorlabs-projects'
    table = dynamodb.Table(table_name)

    # Scan the table for projects
    # Projects now have PK starting with "ORG#" and SK starting with "PROJECT#"
    response = table.scan(
        FilterExpression=Attr('SK').begins_with('PROJECT#') & Attr('PK').begins_with('ORG#')
    )
    
    items = response.get('Items', [])
    
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('SK').begins_with('PROJECT#') & Attr('PK').begins_with('ORG#'),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    return items


# Check for required environment variables
missing_vars = []
if not os.getenv('AWS_ACCESS_KEY_ID'):
    missing_vars.append('AWS_ACCESS_KEY_ID')
if not os.getenv('AWS_SECRET_ACCESS_KEY'):
    missing_vars.append('AWS_SECRET_ACCESS_KEY')
if not CLERK_SECRET_KEY:
    missing_vars.append('CLERK_SECRET_KEY')

if missing_vars:
    st.error(f"Missing environment variables: {', '.join(missing_vars)}")
else:
    with st.spinner("Fetching data..."):
        try:
            # Fetch organizations from Clerk
            orgs_map = fetch_clerk_organizations()
            
            # Fetch projects from DynamoDB
            items = fetch_projects_from_dynamodb()
            
            if not items:
                st.info("No projects found.")
            else:
                # Cache for admin emails
                admin_email_cache = {}
                
                # Build display data
                parsed_projects = []
                for item in items:
                    # Extract org_id from organization_id field or from PK
                    org_id = item.get('organization_id', '')
                    if not org_id:
                        # Try extracting from PK (format: ORG#org_xxx)
                        pk = item.get('PK', '')
                        if pk.startswith('ORG#'):
                            org_id = pk[4:]  # Remove 'ORG#' prefix
                    
                    # Get organization name from Clerk data
                    org_info = orgs_map.get(org_id, {})
                    org_name = org_info.get('name', 'N/A')
                    
                    # Get admin email (with caching)
                    if org_id not in admin_email_cache:
                        admin_email_cache[org_id] = fetch_org_admin_email(org_id)
                    admin_email = admin_email_cache.get(org_id, 'N/A')
                    
                    # Date deployed
                    date_deployed = format_date(item.get('created_at', 'N/A'))
                    
                    # Project name
                    project_name = item.get('name', 'N/A')
                    
                    # Use custom_url if it exists, otherwise function_url
                    url = item.get('custom_url')
                    if not url:
                        url = item.get('function_url', 'N/A')
                    
                    # Status
                    status = item.get('status', 'N/A')
                    
                    parsed_projects.append({
                        "Org ID": org_id,
                        "Organization Name": org_name,
                        "Admin Email": admin_email,
                        "Project Name": project_name,
                        "Status": status,
                        "Date Deployed": date_deployed,
                        "Project URL": url
                    })
                
                if parsed_projects:
                    df = pd.DataFrame(parsed_projects)
                    
                    # Top Level Metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(label="Total Projects", value=len(df))
                    with col2:
                        st.metric(label="Unique Organizations", value=df['Org ID'].nunique())
                    with col3:
                        live_count = len(df[df['Status'] == 'LIVE'])
                        st.metric(label="Live Projects", value=live_count)
                    
                    st.divider()
                    
                    # Display the dataframe
                    st.dataframe(df, use_container_width=True)
                    
                    # CSV Export
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download data as CSV",
                        data=csv,
                        file_name='projects_export.csv',
                        mime='text/csv',
                    )
                    
                    st.success(f"Successfully loaded {len(df)} projects from {df['Org ID'].nunique()} organizations.")
                else:
                    st.info("No projects found.")
                    
        except Exception as e:
            st.error(f"Error: {e}")
