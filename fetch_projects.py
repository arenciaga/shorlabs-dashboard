import boto3
import csv
import json
import os
import requests
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key, Attr

# Load environment variables
load_dotenv()

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")


def fetch_clerk_organizations():
    """Fetch all organizations from Clerk and return a dict mapping org_id -> org_info"""
    if not CLERK_SECRET_KEY:
        print("Warning: CLERK_SECRET_KEY not found. Organization names will not be available.")
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
        
        print(f"Fetched {len(orgs_map)} organizations from Clerk.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching organizations from Clerk: {e}")
    
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
        print(f"Error fetching org memberships for {org_id}: {e}")
    
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
        print(f"Error fetching user {user_id}: {e}")
    
    return None


def fetch_projects():
    # Initialize DynamoDB client
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    table_name = 'shorlabs-projects'
    table = dynamodb.Table(table_name)
    
    print(f"Scanning table {table_name}...")

    # Fetch Clerk organizations first
    print("Fetching organizations from Clerk...")
    orgs_map = fetch_clerk_organizations()

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

    print(f"Found {len(items)} projects.")

    if not items:
        print("No projects found.")
        return

    # Define CSV headers - updated for organization-based model
    fieldnames = [
        "PK", "SK", "organization_id", "created_at", "created_by", "custom_url",
        "env_vars", "ephemeral_storage", "function_name", "function_url", 
        "github_repo", "github_url", "memory", "migrated_at", "name", 
        "project_id", "root_directory", "start_command", "status", 
        "subdomain", "timeout", "updated_at"
    ]

    output_file = 'projects.csv'
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for item in items:
            row = {}
            for field in fieldnames:
                if field in item:
                    val = item[field]
                    if field == 'env_vars' and isinstance(val, dict):
                        row[field] = json.dumps(val)
                    else:
                        row[field] = val
                else:
                    row[field] = ""
            
            writer.writerow(row)

    print(f"Successfully wrote data to {output_file}\n")

    # Defined headers and column widths for the terminal output
    # Updated: Org ID, Organization Name, Admin Email, Date Deployed, Project URL
    headers = ["Org ID", "Organization Name", "Admin Email", "Date Deployed", "Project URL"]
    # min widths
    widths = [35, 25, 30, 25, 45]

    # Cache for admin emails to avoid repeated API calls
    admin_email_cache = {}

    # detailed_projects list for display
    display_rows = []
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
        date_deployed = item.get('created_at', 'N/A')
        
        # Use custom_url if it exists, otherwise function_url
        url = item.get('custom_url')
        if not url:
            url = item.get('function_url', 'N/A')
        
        display_rows.append([org_id, org_name, admin_email, date_deployed, url])
        
        # dynamic width adjustment
        widths[0] = max(widths[0], len(str(org_id)))
        widths[1] = max(widths[1], len(str(org_name)))
        widths[2] = max(widths[2], len(str(admin_email)))
        widths[3] = max(widths[3], len(str(date_deployed)))
        widths[4] = max(widths[4], len(str(url)))

    # Create format string
    fmt = "  ".join([f"{{:<{w}}}" for w in widths])

    # Print Table
    print("-" * (sum(widths) + 8))
    print(fmt.format(*headers))
    print("-" * (sum(widths) + 8))
    
    for row in display_rows:
        print(fmt.format(*row))
    print("-" * (sum(widths) + 8))


if __name__ == "__main__":
    fetch_projects()
