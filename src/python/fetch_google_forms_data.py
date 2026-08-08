import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import text

import config
from logger_config import setup_logger

logger = setup_logger(__name__, 'fetch_google_forms_data.log')

engine = config.get_engine()  # requires the Postgres container to be running


def test_network_connectivity() -> None:
    """Test if we can reach Google's servers with proper SSL context"""
    logger.info("Testing network connectivity to Google services")
    import socket
    import ssl

    test_hosts = [
        ('accounts.google.com', 443, '/.well-known/openid-configuration'),
        ('sheets.googleapis.com', 443, '/$discovery/rest?version=v4'),
        ('www.google.com', 443, '/')
    ]

    for host, port, path in test_hosts:
        try:
            logger.info(f"Testing connection to {host}:{port}...")

            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED

            with socket.create_connection((host, port), timeout=10) as sock:
                logger.debug(f"TCP connection to {host}:{port} successful")

                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    logger.debug(f"SSL handshake successful. Protocol: {ssock.version()}")

                    request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
                    ssock.sendall(request.encode())
                    response = ssock.recv(4096).decode()
                    status_line = response.split('\r\n')[0]
                    logger.debug(f"HTTP request successful. Status: {status_line}")

        except Exception as e:
            logger.error(f"Error connecting to {host}:{port}: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())


def fetch_google_sheet_data(range_name: str = None) -> pd.DataFrame:
    """Read form responses from the Google Sheet into a normalised DataFrame."""
    range_name = range_name or config.GOOGLE_SHEET_RANGE
    sheet_id = config.google_sheet_id()
    credentials_path = config.GOOGLE_CREDENTIALS_PATH

    if not credentials_path.exists():
        raise ValueError(
            f"Google Cloud credentials file not found at: {credentials_path}\n"
            "Please follow these steps to set up credentials:\n"
            "1. Go to Google Cloud Console (https://console.cloud.google.com/)\n"
            "2. Create a new project or select an existing one\n"
            "3. Enable the Google Sheets API\n"
            "4. Create a service account and download the JSON key file\n"
            f"5. Save the file as 'credentials.json' at: {credentials_path.parent}"
        )

    creds = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'],
    )
    service = build('sheets', 'v4', credentials=creds,
                    cache_discovery=False, static_discovery=False)

    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_name
    ).execute()
    values = result.get('values', [])

    if not values:
        return pd.DataFrame()

    df = pd.DataFrame(values[1:], columns=values[0])
    df.rename(columns={
        'Timestamp': 'registered_at',
        "Tag line (e.g #EUW) ": "player_tag",
        "Summoner ID (case sensitive)": "summ_id",
        "Region": "region",
    }, inplace=True)

    df['registered_at'] = pd.to_datetime(df['registered_at'], errors='coerce')
    df['player_tag'] = df['player_tag'].str.lstrip("#").str.strip()
    df['summ_id'] = df['summ_id'].str.strip()

    # Drop submissions we cannot build a Riot ID from.
    df = df[df['summ_id'].notna() & (df['summ_id'] != '')]
    df = df[df['player_tag'].notna() & (df['player_tag'] != '')]

    return df.sort_values('registered_at')


def upsert_players(df: pd.DataFrame) -> int:
    """Insert any player not already registered. Returns the number added.

    Keyed on the Riot ID rather than sheet position, so re-ordering or deleting
    rows in the sheet can no longer reassign a player's ELO history.
    """
    if df.empty:
        logger.info("No form responses to load")
        return 0

    statement = text("""
        INSERT INTO public.players (summ_id, player_tag, region, registered_at)
        VALUES (:summ_id, :player_tag, :region, :registered_at)
        ON CONFLICT (lower(summ_id), lower(player_tag)) DO NOTHING
    """)

    records = df[['summ_id', 'player_tag', 'region', 'registered_at']].to_dict('records')
    for record in records:
        if pd.isna(record['registered_at']):
            record['registered_at'] = None

    with engine.begin() as connection:
        result = connection.execute(statement, records)
        inserted = result.rowcount if result.rowcount and result.rowcount > 0 else 0

    logger.info(f"{inserted} new player(s) registered out of {len(records)} responses")
    return inserted


def main():
    logger.info("Starting Google Forms data fetch process")
    df = fetch_google_sheet_data()
    if df.empty:
        logger.warning("No data was fetched from Google Sheets")
        return

    logger.info(f"Fetched {len(df)} valid entries from Google Sheets")
    upsert_players(df)
    logger.info("Google Forms data fetch process completed")


if __name__ == "__main__":
    try:
        test_network_connectivity()
        main()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        print("\nTroubleshooting steps:")
        print("1. Verify your internet connection")
        print("2. Check if the Google Sheet ID is correct and shared with the service account")
        print("3. Ensure the Google Sheets API is enabled in your Google Cloud project")
        print("4. Verify the service account has the correct permissions")
        print("5. Check if your system time is synchronized")
        raise
