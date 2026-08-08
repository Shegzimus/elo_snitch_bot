# ELO Snitch Bot

A data pipeline to track and report on the ELO progress of members of the League of Naija group chat using a combination of Airflow, Python, node.js, and WhatsApp Web API.

On launch, members of the gc were able to type commands which generated a table of elo changes for each member of the group chat who had registered in a Google form I shared with them. My machine was prod. I should probably look for a cheap way to host.

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
├── sql/migrations/       # Ordered, re-runnable schema migrations
├── .env                  # Environment variables
├── Dockerfile            # Docker configuration
└── docker-compose.yaml   # Docker Compose configuration
```

## Installation

1. Clone the repository
2. Create and configure your `.env` file as described above
3. Start Postgres:
```bash
docker compose up -d pgdatabase
```
   If port 5432 is already taken by another project, set `POSTGRES_PORT` in a
   `.env` at the repo root (for compose) **and** in `config/.env` (for the
   Python client) so the two agree:
```bash
POSTGRES_PORT=5433 docker compose up -d pgdatabase
```
4. Apply database migrations, in order:
```bash
docker exec -i <postgres-container> psql -U root -d snitch_bot_db \
  -v ON_ERROR_STOP=1 < sql/migrations/001_consolidate_players.sql
```
   Then sanity-check the result — every count in the output should show zero
   orphans before you rely on it:
```bash
docker exec -i <postgres-container> psql -U root -d snitch_bot_db \
  < sql/migrations/001_verify.sql
```
5. Start the WhatsApp bot (from the repo root):
```bash
npm install && npm start
```

### Player identity

Players live in a single `players` table keyed on their Riot ID
(`summ_id` + `player_tag`). Earlier versions keyed players on the *row index of
the Google Sheet*, which meant deleting or reordering a sheet row silently
reassigned that player's entire ELO history to someone else. `001` migrates off
that scheme; `players.legacy_id` retains the old index for auditing only.

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

## Ports

Two `.env` files, deliberately separate:

| File | Read by | Purpose |
|---|---|---|
| `.env` (repo root) | docker compose only | host port substitution in `docker-compose.yaml` |
| `config/.env` | the Python pipeline | Riot/Google credentials, DB connection |

`POSTGRES_PORT` must be set to the same value in both, or the pipeline will
connect to a different database than the one compose published.

Defaults are `POSTGRES_PORT=5432` and `PGADMIN_PORT=5051`. Override in the root
`.env` when another project already binds those.

## pgAdmin

Browse to `http://localhost:${PGADMIN_PORT}` and log in with
`PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` from `config/pgadmin.env`.

The `snitch_bot` server is preregistered from `config/pgadmin_servers.json`.
Expanding it prompts once for the Postgres password (`POSTGRES_USER`'s password,
`root` by default) — tick *Save Password* to be asked only once.

Note that pgAdmin reads **only** `PGADMIN_*` variables. The `DB_HOST`/`DB_PORT`/
`DB_USER`/`DB_PASS`/`DB_NAME` entries in `config/pgadmin.env` are inert; the
connection is defined in `pgadmin_servers.json` instead. That file uses the
compose service name `pgdatabase` and its **internal** port 5432, not the
published host port.

## Troubleshooting

- If you encounter Google API authentication issues, verify your credentials in the `.env` file
- For Riot API rate limiting issues, consider implementing a retry mechanism or increasing the delay between API calls
- Check Docker logs for detailed error messages: `docker-compose logs`

