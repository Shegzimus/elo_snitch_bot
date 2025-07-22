import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from sqlalchemy import create_engine

# Define the path to the .env file from the project root directory
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env"))

# Check if .env file exists
if not os.path.exists(env_path):
    raise FileNotFoundError(f"Could not find .env file at: {env_path}")

# Load environment variables from .env file
load_dotenv(dotenv_path=env_path, override=True)

# Print all environment variables for debugging
# print("Environment variables:", os.environ)
# print(f"Google Sheet ID from .env: {os.getenv('google_sheet_id')}")

engine:object = create_engine("postgresql://root:root@localhost:5432/snitch_bot_db") # will only work if the Postgres DB container is running

def test_network_connectivity()-> None:
    """Test if we can reach Google's servers with proper SSL context"""
    import socket
    import ssl
    
    test_hosts = [
        ('accounts.google.com', 443, '/.well-known/openid-configuration'),
        ('sheets.googleapis.com', 443, '/$discovery/rest?version=v4'),
        ('www.google.com', 443, '/')
    ]
    
    for host, port, path in test_hosts:
        try:
            print(f"\nTesting connection to {host}:{port}...")
            
            # Create SSL context with modern settings
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            # Test TCP connection
            with socket.create_connection((host, port), timeout=10) as sock:
                print(f"TCP connection to {host}:{port} successful")
                
                # Test SSL handshake
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    print(f"SSL handshake successful. Protocol: {ssock.version()}")
                    
                    # Test HTTP request
                    request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
                    ssock.sendall(request.encode())
                    response = ssock.recv(4096).decode()
                    status_line = response.split('\r\n')[0]
                    print(f"HTTP request successful. Status: {status_line}")
                    
        except Exception as e:
            print(f"Error connecting to {host}:{port}: {str(e)}")
            import traceback
            traceback.print_exc()

def create_google_sheets_service(credentials_path: str)-> object:
    """Create and return an authorized Google Sheets API service instance."""
    try:
        # Get the absolute path to the credentials file
        credentials_path = os.path.abspath(credentials_path)
        print(f"Using credentials from: {credentials_path}")
        
        # Load the service account credentials
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        # Build the service
        service = build('sheets', 'v4', credentials=creds, 
                       cache_discovery=False,  # Avoids an unnecessary request
                       static_discovery=False)  # Uses the discovery document from the package
        
        return service
    except Exception as e:
        print(f"Error creating Google Sheets service: {str(e)}")
        raise

def fetch_google_sheet_data(
        range_name: str = "Form Responses 1!A:D", 
        credentials_path: str = None
    ) -> pd.DataFrame:
    
    sheet_id:str = os.getenv("google_sheet_id")
    
    if not sheet_id:
        raise ValueError("Google Sheet ID is not set in environment variables.")

    # Handle credentials path
    if not credentials_path:
        # Default to .google/credentials.json in the project root
        credentials_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", ".google", "credentials.json"
        ))
    
    # print(f"Looking for credentials at: {credentials_path}")
    if not os.path.exists(credentials_path):
        raise ValueError(
            f"Google Cloud credentials file not found at: {credentials_path}\n"
            "Please follow these steps to set up credentials:\n"
            "1. Go to Google Cloud Console (https://console.cloud.google.com/)\n"
            "2. Create a new project or select an existing one\n"
            "3. Enable the Google Sheets API\n"
            "4. Create a service account and download the JSON key file\n"
            f"5. Save the file as 'credentials.json' in the '.google' directory at: {os.path.dirname(credentials_path)}"
        )

    # Define the required scope
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    # Load credentials from the service account file
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES)

    # Build the Sheets API service
    service:object = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet:object = service.spreadsheets()
    result:object = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
    values:list[list[str]] = result.get('values', [])

    # Minor transformations
    values_df:pd.DataFrame = pd.DataFrame(values[1:], columns=values[0])  # Convert to DataFrame
    values_df.rename(columns={
        'index': 'id',
        'Timestamp': 'timestamp',  
        "Tag line (e.g #EUW) ": "player_tag",
        "Summoner ID (case sensitive)": "summ_id",
        "Region": "region"
    }, inplace=True)

    values_df['timestamp'] = pd.to_datetime(values_df['timestamp'], errors='coerce')  # Convert timestamp to datetime
    values_df['player_tag'] = values_df['player_tag'].str.lstrip("#")  # Strip '#' from player_tag

    return values_df

def load_to_db(df: pd.DataFrame, table_name: str, db_connection:object= engine) -> None:   # using a connection object argument instead of a hard-coded engine in case we want to use a cloud database in the future
    if df.empty:
        print("No data to load.")
        return
    
    df.head(0).to_sql(name=table_name, con=db_connection, if_exists='replace')
    print("Table header created successfully")

    df.to_sql(name=table_name, con=db_connection, if_exists='replace')

    return None

def main():
    df = fetch_google_sheet_data()
    if df.empty:
        print("No data fetched from Google Sheets.")
    else:
        print("Data fetched successfully.")
        print(df)
        load_to_db(df, table_name="form_responses", db_connection=engine)  # Load to database






if __name__ == "__main__":
    try:
        # Test network connectivity first
        test_network_connectivity()
        
        # Then run the main function
        main()
    except Exception as e:
        print(f"\n An error occurred: {str(e)}")
        print("\n Troubleshooting steps:")
        print("1. Verify your internet connection")
        print("2. Check if the Google Sheet ID is correct and shared with the service account")
        print("3. Ensure the Google Sheets API is enabled in your Google Cloud project")
        print("4. Verify the service account has the correct permissions")
        print("5. Check if your system time is synchronized")
        print("\nFor more detailed error information, check the full traceback above.")
        raise