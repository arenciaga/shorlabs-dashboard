import streamlit as st
import boto3
import pandas as pd
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key, Attr

load_dotenv()

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

st.set_page_config(page_title="Services Dashboard", layout="wide")
st.title("Services Dashboard")


def format_date(iso_date_str):
    if not iso_date_str or iso_date_str == 'N/A':
        return 'N/A'
    try:
        dt = datetime.fromisoformat(iso_date_str.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y %I:%M %p')
    except (ValueError, AttributeError):
        return iso_date_str


@st.cache_data(ttl=300)
def fetch_clerk_organizations():
    if not CLERK_SECRET_KEY:
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

        orgs_list = orgs_data if isinstance(orgs_data, list) else orgs_data.get('data', [])

        for org in orgs_list:
            org_id = org.get('id')
            if org_id:
                orgs_map[org_id] = {'name': org.get('name', 'N/A')}
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching organizations from Clerk: {e}")

    return orgs_map


def fetch_org_admin_email(org_id):
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

        memberships = memberships_data if isinstance(memberships_data, list) else memberships_data.get('data', [])

        for membership in memberships:
            role = membership.get('role', '')
            if role in ('org:admin', 'admin'):
                public_user_data = membership.get('public_user_data', {})
                email = public_user_data.get('identifier')
                if not email:
                    user_id = public_user_data.get('user_id')
                    if user_id:
                        email = fetch_user_email(user_id)
                return email or "N/A"

        if memberships:
            email = memberships[0].get('public_user_data', {}).get('identifier')
            return email or "N/A"

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching memberships for {org_id}: {e}")

    return "N/A"


def fetch_user_email(user_id):
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
                for e in email_addresses:
                    if e.get('id') == primary_id:
                        return e.get('email_address')
            return email_addresses[0].get('email_address')
    except requests.exceptions.RequestException:
        pass

    return None


@st.cache_data(ttl=300)
def fetch_services_from_dynamodb():
    """Fetch all service records from DynamoDB.
    Services have SK matching the pattern PROJECT#...#SERVICE#...
    and entity_type == 'service'.
    """
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    table = dynamodb.Table('shorlabs-projects')

    # Services have entity_type == 'service' and SK contains '#SERVICE#'
    response = table.scan(
        FilterExpression=Attr('entity_type').eq('service') & Attr('PK').begins_with('ORG#')
    )

    items = response.get('Items', [])

    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('entity_type').eq('service') & Attr('PK').begins_with('ORG#'),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    return items


# ── Env check ────────────────────────────────────────────────────────────────
missing_vars = [v for v in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'CLERK_SECRET_KEY')
                if not os.getenv(v)]

if missing_vars:
    st.error(f"Missing environment variables: {', '.join(missing_vars)}")
else:
    with st.spinner("Fetching data..."):
        try:
            orgs_map = fetch_clerk_organizations()
            items = fetch_services_from_dynamodb()

            if not items:
                st.info("No services found.")
            else:
                admin_email_cache = {}
                parsed_services = []

                for item in items:
                    # ── Org info ──────────────────────────────────────────
                    org_id = item.get('organization_id', '')
                    if not org_id:
                        pk = item.get('PK', '')
                        if pk.startswith('ORG#'):
                            org_id = pk[4:]

                    org_name = orgs_map.get(org_id, {}).get('name', 'N/A')

                    if org_id not in admin_email_cache:
                        admin_email_cache[org_id] = fetch_org_admin_email(org_id)
                    admin_email = admin_email_cache.get(org_id, 'N/A')

                    # ── Service fields ────────────────────────────────────
                    service_type = item.get('service_type', 'N/A')  # 'web-app' | 'database'
                    service_name = item.get('name', 'N/A')
                    service_id   = item.get('service_id', item.get('SK', 'N/A'))
                    project_id   = item.get('project_id', 'N/A')
                    status       = item.get('status', 'N/A')
                    github_repo  = item.get('github_repo', '')
                    github_url   = item.get('github_url', '')
                    memory       = item.get('memory', 'N/A')
                    start_cmd    = item.get('start_command', 'N/A')
                    date_created = format_date(item.get('created_at', 'N/A'))
                    date_updated = format_date(item.get('updated_at', 'N/A'))

                    # URL: custom > function_url (web-app only)
                    url = item.get('custom_url') or item.get('function_url', 'N/A')

                    # ── Database-specific fields ──────────────────────────
                    db_endpoint = item.get('db_endpoint', '')
                    db_name     = item.get('db_name', '')
                    db_port     = item.get('db_port', '')
                    db_cluster  = item.get('db_cluster_identifier', '')

                    parsed_services.append({
                        "Org ID":           org_id,
                        "Organization":     org_name,
                        "Admin Email":      admin_email,
                        "Service Name":     service_name,
                        "Service Type":     service_type,
                        "Status":           status,
                        "Project ID":       project_id,
                        "Service ID":       service_id,
                        "URL":              url,
                        "GitHub Repo":      github_repo,
                        "GitHub URL":       github_url,
                        "Memory (MB)":      memory,
                        "Start Command":    start_cmd,
                        "DB Endpoint":      db_endpoint,
                        "DB Name":          db_name,
                        "DB Port":          db_port,
                        "DB Cluster":       db_cluster,
                        "Created At":       date_created,
                        "Updated At":       date_updated,
                    })

                if not parsed_services:
                    st.info("No services found.")
                else:
                    df = pd.DataFrame(parsed_services)

                    # ── Metrics ───────────────────────────────────────────
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Total Services", len(df))
                    with col2:
                        st.metric("Unique Orgs", df['Org ID'].nunique())
                    with col3:
                        st.metric("Live Services", len(df[df['Status'] == 'LIVE']))
                    with col4:
                        st.metric("Web Apps", len(df[df['Service Type'] == 'web-app']))
                    with col5:
                        st.metric("Databases", len(df[df['Service Type'] == 'database']))

                    st.divider()

                    # ── Filters ───────────────────────────────────────────
                    fcol1, fcol2, fcol3 = st.columns(3)
                    with fcol1:
                        type_filter = st.multiselect(
                            "Service Type",
                            options=sorted(df['Service Type'].dropna().unique()),
                            default=[]
                        )
                    with fcol2:
                        status_filter = st.multiselect(
                            "Status",
                            options=sorted(df['Status'].dropna().unique()),
                            default=[]
                        )
                    with fcol3:
                        org_filter = st.multiselect(
                            "Organization",
                            options=sorted(df['Organization'].dropna().unique()),
                            default=[]
                        )

                    filtered_df = df.copy()
                    if type_filter:
                        filtered_df = filtered_df[filtered_df['Service Type'].isin(type_filter)]
                    if status_filter:
                        filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
                    if org_filter:
                        filtered_df = filtered_df[filtered_df['Organization'].isin(org_filter)]

                    st.caption(f"Showing {len(filtered_df)} of {len(df)} services")

                    # ── Tabbed views: Web Apps vs Databases ───────────────
                    tab_all, tab_web, tab_db = st.tabs(["All Services", "Web Apps", "Databases"])

                    WEB_COLS = ["Organization", "Admin Email", "Service Name", "Status",
                                "URL", "GitHub Repo", "Memory (MB)", "Start Command",
                                "Created At", "Updated At"]
                    DB_COLS  = ["Organization", "Admin Email", "Service Name", "Status",
                                "DB Cluster", "DB Endpoint", "DB Name", "DB Port",
                                "Created At", "Updated At"]

                    with tab_all:
                        st.dataframe(filtered_df, use_container_width=True)

                    with tab_web:
                        web_df = filtered_df[filtered_df['Service Type'] == 'web-app']
                        available = [c for c in WEB_COLS if c in web_df.columns]
                        st.dataframe(web_df[available], use_container_width=True)

                    with tab_db:
                        db_df = filtered_df[filtered_df['Service Type'] == 'database']
                        available = [c for c in DB_COLS if c in db_df.columns]
                        st.dataframe(db_df[available], use_container_width=True)

                    st.divider()

                    # ── CSV export ────────────────────────────────────────
                    csv = filtered_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download filtered data as CSV",
                        data=csv,
                        file_name='services_export.csv',
                        mime='text/csv',
                    )

        except Exception as e:
            st.error(f"Error: {e}")
            st.exception(e)
