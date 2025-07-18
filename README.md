# ELO Snitch Bot

A data pipeline to track and report on the ELO progress of members of the League of Naija group chat using a combination of Airflow, Python, node.js, and WhatsApp Web API.

Developer hours wasted: [![wakatime](https://wakatime.com/badge/user/7bb4aa36-0e0a-4c8e-9ce5-180c23c37a37/project/3587c415-099d-40f9-afd5-0869b61cfe72.svg)](https://wakatime.com/badge/user/7bb4aa36-0e0a-4c8e-9ce5-180c23c37a37/project/3587c415-099d-40f9-afd5-0869b61cfe72)

## Prerequisites

Before running the bot, ensure you have the following installed:

1. **Docker and Docker Compose**
   - Install Docker Desktop from [here](https://www.docker.com/products/docker-desktop)
   - Ensure Docker Compose is included in your installation

2. **Google API Credentials**
   - Create a Google Cloud project
   - Enable Google Forms API and Google Sheets API
   - Create credentials (OAuth 2.0 Client ID)
   - Download credentials JSON file, rename it to credentials.json and place it in the .google directory.

3. **Riot Games API Key**
   - Register at [Riot Games Developer Portal](https://developer.riotgames.com/)
   - Generate a developer API key, rename it to riot_api_key and place it in the .env directory.
  
4. **WhatsApp Group ID**
   - Open your WhatsApp group of choice on WhatsApp Web
   - Inspect the page elements of the group chat
   - Copy the group ID from the HTML element with the class name 'chat-title'
   - Declare it as whatsapp_group_id in the .env directory.
   
## Environment Setup

1. Create a `.env` file in the config directory with the following variables:
```
# Google API Credentials
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
GOOGLE_FORM_ID=your_form_id
GOOGLE_SHEET_ID=your_sheet_id

# Riot Games API
RIOT_API_KEY=your_riot_api_key
RIOT_REGION=na1

# Airflow Configuration
AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW__CORE__EXECUTOR=LocalExecutor
```
## Directory Structure

```
elo_snitch_bot/
├── assets/               # Static assets
├── config/               # Configuration files
├── dags/                 # Airflow DAG definitions
├── data/                 # Data storage directory
│   └── elo_changes/      # ELO change history
├── docker/               # Docker configuration
├── logs/                 # Application logs
├── node_modules/         # JavaScript dependencies
├── plugins/              # Custom plugins
├── sql/                  # SQL scripts
├── src/
│   ├── python/           # Python source code
│   │   ├── generate_puuid.py  # Player PUUID generation
│   │   ├── elo_check.py       # ELO checking
│   │   └── elo_tracker.py     # ELO tracking and reporting
│   └── js/               # JavaScript source code
│       └── whatsapp_bot.js    # WhatsApp bot implementation
├── .env                  # Environment variables
├── Dockerfile            # Docker configuration
└── docker-compose.yaml   # Docker Compose configuration
```

## Installation

1. Clone the repository
2. Create and configure your `.env` file as described above
3. Build and start the Docker containers:
```bash
docker-compose up --build
```

## Accessing the Application

Once the containers are running:
1. Access Airflow UI at http://localhost:8080
2. Default credentials:
   - Username: admin
   - Password: admin


## Pipeline Overview

The bot runs hourly and executes the following tasks in sequence:
1. `fetch_google_forms_data.py` - Fetch player data from Google Forms
2. `generate_puuid.py` - Generate PUUIDs for players
3. `elo_check.py` - Check current ELO for all players
4. `elo_tracker.py` - Track and report ELO changes

## Troubleshooting

- If you encounter Google API authentication issues, verify your credentials in the `.env` file
- For Riot API rate limiting issues, consider implementing a retry mechanism or increasing the delay between API calls
- Check Docker logs for detailed error messages: `docker-compose logs`

