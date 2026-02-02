import boto3
import csv
import os
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key, Attr

# Load environment variables
load_dotenv()

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

    # Scan the table
    # We filter specifically for projects. 
    # Based on the provided data struct:
    # Projects have SK starting with "PROJECT#" and PK starting with "USER#"
    # Deployments have PK starting with "PROJECT#"
    
    # Using a FilterExpression to only get projects
    # We check if SK begins with 'PROJECT#'
    # Note: Scanning is expensive on large tables, but for a script like this it's usually what is intended unless we know specific User IDs.
    response = table.scan(
        FilterExpression=Attr('SK').begins_with('PROJECT#')
    )
    
    items = response.get('Items', [])
    
    # Handle pagination if permitted/needed (Loop until LastEvaluatedKey is empty)
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('SK').begins_with('PROJECT#'),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))

    print(f"Found {len(items)} projects.")

    if not items:
        print("No projects found.")
        return

    # Define CSV headers based on the prompt's example
    fieldnames = [
        "PK", "SK", "build_id", "created_at", "custom_url", "deploy_id", 
        "ecr_repo", "env_vars", "ephemeral_storage", "finished_at", 
        "function_name", "function_url", "github_repo", "github_url", 
        "logs_url", "memory", "name", "project_id", "root_directory", 
        "start_command", "started_at", "status", "subdomain", "timeout", 
        "updated_at", "user_id"
    ]

    output_file = 'projects.csv'
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for item in items:
            # Create a row dictionary, handling missing keys
            row = {}
            for field in fieldnames:
                # DynamoDB might return Decimal types or others, standardizing to string might be safer for CSV
                # But DictWriter handles basic types well.
                # However, nested objects like 'env_vars' might come out as dictionaries.
                # In the prompt, env_vars looks like a JSON string or string representation of a dict.
                # If it's a Map in DynamoDB, boto3 deserializes it to a dict.
                if field in item:
                    val = item[field]
                    if field == 'env_vars' and isinstance(val, dict):
                         # If it's a dictionary, maybe stringify it to match the CSV format implied
                         import json
                         row[field] = json.dumps(val)
                    else:
                        row[field] = val
                else:
                    row[field] = ""
            
            writer.writerow(row)

    print(f"Successfully wrote data to {output_file}\n")

    # Defined headers and column widths for the terminal output
    headers = ["User ID", "Project ID", "Date Deployed", "Project URL"]
    # min widths
    widths = [20, 15, 25, 40] 

    # detailed_projects list for display
    display_rows = []
    for item in items:
        u_id = item.get('user_id', 'N/A')
        p_id = item.get('project_id', 'N/A')
        c_at = item.get('created_at', 'N/A')
        # Use custom_url if it exists, otherwise function_url, otherwise N/A
        url = item.get('custom_url')
        if not url:
            url = item.get('function_url', 'N/A')
        
        display_rows.append([u_id, p_id, c_at, url])
        
        # dynamic width adjustment
        widths[0] = max(widths[0], len(u_id))
        widths[1] = max(widths[1], len(p_id))
        widths[2] = max(widths[2], len(c_at))
        widths[3] = max(widths[3], len(url))

    # Create format string
    fmt = f"{{:<{widths[0]}}}  {{:<{widths[1]}}}  {{:<{widths[2]}}}  {{:<{widths[3]}}}"

    # Print Table
    print("-" * (sum(widths) + 6))
    print(fmt.format(*headers))
    print("-" * (sum(widths) + 6))
    
    for row in display_rows:
        print(fmt.format(*row))
    print("-" * (sum(widths) + 6))

if __name__ == "__main__":
    fetch_projects()
