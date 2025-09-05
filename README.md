# Fuzzed Records

Fuzzed Records is a modern music platform that integrates decentralized authentication with music streaming. It allows users to explore a library of songs and manage their profiles. The platform leverages **Nostr Wallet** for decentralized authentication and **Wavlake** for music distribution by Fuzzed Records.

---

## Table of Contents
1. [Features](#features)
2. [Technologies Used](#technologies-used)
3. [File Structure](#file-structure)
4. [Setup and Deployment](#setup-and-deployment)
5. [API Endpoints](#api-endpoints)
6. [Workflow](#workflow)
7. [License](#license)
8. [Acknowledgments](#acknowledgments)

---

## Features

- **Music Library**: Browse and play songs hosted on Wavlake. The library includes detailed artist and album information.
- **User Profiles**: Authenticate using Nostr Wallet to view and manage your profile, leveraging Nostr NIP-07 for login.
- **NIP-19 Profile Lookup**: Retrieve metadata using Nostr `nprofile` strings.
- **Decentralized Authentication**: Uses Nostr Wallet for secure, decentralized user authentication.
- **Responsive Design**: Optimized for both desktop and mobile devices.
- **Efficient Data Caching**: Utilizes caching for optimizing data retrieval performance.
- **Rate Limiting**: Protects API endpoints using Flask-Limiter with optional Azure Table Storage backend (ASGI-compatible).
- **Relay Management**: Users can add relay URLs through the `/update-relays` endpoint.
- **CORS Configuration**: Allowed origins can be customized via environment variable (Flask-CORS works under Hypercorn).
- **Section Links**: Use URL hashes like `/#gear` to open a specific section directly.
- **Fuzzed Guitars**: Boutique gear prototypes can be viewed in the Gear section (`/#gear`), via the `fuzzedguitars` subdomain, or using the `/fuzzedguitars` path.
- **Shop**: After Nostr login, visit `/shop` to browse custom guitars and pay via Lightning.

---

## Technologies Used

- **Frontend**:
  - HTML, CSS, JavaScript
  - Embedded Wavlake player
- **Backend**:
  - Flask (Python)
  - Flask-RESTful for API endpoints
  - Pynostr for Nostr relay interactions
- **Authentication**:
  - Nostr Wallet for decentralized authentication
  - NIP-07 compatible wallet integration for user login
  - NIP-05 verification for admin access
- **Hosting**:
  - Microsoft Azure
  - Hypercorn ASGI server

---

## Configuration

Set the following environment variables to configure the application:

- RELAY_URLS: Comma-separated list of Nostr relay URLs (default: wss://relay.damus.io,wss://relay.primal.net,wss://relay.nostr.pub,wss://nos.lol). If unset and no relay list files exist, this default list populates `ACTIVE_RELAYS`.
- CACHE_TIMEOUT: Seconds to cache fetched user profiles (default: 300)
- REQUIRED_DOMAIN: Domain for NIP-05 profile verification (default: fuzzedrecords.com)
- MAX_CONTENT_LENGTH: Max request payload size in bytes (default: 1048576)
- FRONTEND_ORIGINS: Comma-separated list of allowed CORS origins (default: '*')
- AZURE_TABLES_CONNECTION_STRING: Azure connection string for rate-limit storage
- RATELIMIT_TABLE_NAME: Azure table name for rate-limit counters (default: RateLimit)
- Rate-limit keys are percent-encoded before being stored in Azure Table Storage.
- RATELIMIT_STORAGE_URI: Alternate limiter storage URI (default: memory://)
- WAVLAKE_API_BASE: Base URL for Wavlake API (default: https://wavlake.com/api/v1)
- HTTP_TIMEOUT: Timeout in seconds for external API requests such as Wavlake and Azure Graph (default: 5)
- TRACK_CACHE_TIMEOUT: Seconds to cache the music library before background refresh (default: 300)
- SEARCH_TERM: Search term used to filter Wavlake artists (default: " by Fuzzed Records")
- PROFILE_FETCH_TIMEOUT: Seconds to wait for a user profile event when handling `/fetch-profile`, `/fetch-nprofile`, or `/validate-profile` (default: 5)
- RELAY_CONNECT_TIMEOUT: Seconds allowed to establish each WebSocket connection to a relay (default: 2)
- DISABLE_TLS_VERIFY: Set to 1 to disable TLS certificate verification when connecting to relays (default: 0). **Insecure - only use for testing; a warning is logged when enabled.**
- WALLET_PRIVKEY_HEX: Private key for the server wallet. May be provided as a hex
  string or NIP-19 `nsec` value. The corresponding public key is derived automatically
  and exposed to the frontend as `serverWalletPubkey`.
- TENANT_ID: Azure AD Tenant ID for discovery JSON endpoint (/.well-known/nostr.json)
- CLIENT_ID: Azure AD Application (client) ID
- CLIENT_SECRET: Azure AD Application client secret
- (Optional) LOG_LEVEL: Python log level for application logging (default: DEBUG)
- (Optional) FLASK_DEBUG: Set to 1 or true for debug mode when running locally

---

## File Structure

```
./
├── app.py                    # Top-level Flask router (imports modular routes)
├── azure_resources.py        # MSAL & Nostr discovery JSON endpoint
├── azure_storage_limiter.py  # Azure Table Storage backend for rate limiting (keys percent-encoded)
├── nostr_utils.py            # Nostr endpoints: /fetch-profile, /validate-profile
├── wavlake_utils.py          # Wavlake API helpers and /tracks endpoint
├── relay_checker.py          # Relay maintenance script
├── requirements.txt          # Python dependencies
├── startup.sh                # Deployment script for Azure
├── templates/
│   └── index.html            # Main HTML file for the website
└── static/
    ├── style.css             # CSS for styling the website (committed)
    ├── images/               # Site images and icons
    └── scripts/
        ├── auth.js           # Frontend NIP-07 authentication logic
        ├── tracks.js         # Frontend music library display logic
        └── utils.js          # Shared JavaScript helper functions
```

---

## Setup and Deployment

### Prerequisites
- Python 3.11 or newer *(older versions fail due to type-hint syntax)*
- Nostr Wallet (for authentication)
- Microsoft Azure account (for deployment)

### Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-repo/fuzzedrecords.git
   cd fuzzedrecords
   ```

2. **Set Up Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   > **Note**: `static/style.css` is committed; no Sass/SCSS compilation is required.
4. **Run Tests**:
   ```bash
   pytest
   ```
   All tests should pass before deployment.
5. **Run the Application Locally**:
   ```bash
   python app.py
   ```
6. **Deploy to Azure**:
   - Ensure `startup.sh` is executable:
     ```bash
     chmod +x startup.sh
     ```
   - Create a `runtime.txt` file in the project root containing `python-3.11`
     so Azure uses the correct Python version.
   - `startup.sh` installs Python dependencies and then launches the server.
   - Deploy the app to Azure WebApp using the Azure CLI or portal.
    > **Note**: The application must be able to establish outbound WebSocket connections to the relays listed in `RELAY_URLS`. Blocked outbound traffic will result in profile fetch failures.
7. **Maintain Relay Lists**:
   - Run `python relay_checker.py` periodically to update `good-relays.txt`.
   - On startup the app loads relays from `good-relays.txt` if present, falling back to `relays.txt` or the `RELAY_URLS` environment variable.
  - Users can contribute relays via the `/update-relays` endpoint; submitted URLs are merged in-memory and written back to `relays.txt`.
8. **Build and Run with Docker**:
   ```bash
   docker build -t fuzzedrecords .
   docker run --rm -p 8000:8000 fuzzedrecords
   ```
   The app will be available at http://localhost:8000.

---

## Testing

Install the required packages and run the test suite:

```bash
pip install -r requirements.txt
pytest
```

If dependencies are missing, tests will fail with import errors similar to the ones observed when `flask` or `websockets` are not installed.

## API Endpoints

All backend routes are now synchronous Flask handlers. Asynchronous Nostr operations are executed internally using `asyncio.run()`, so clients interact with a standard blocking HTTP API.

### 0. Nostr Discovery JSON
- **Endpoint**: `/.well-known/nostr.json`
- **Method**: `GET`
- **Description**: Returns discovery information for a single administrator. The request must include a `name` query parameter matching the user's display name. If omitted, the endpoint responds with HTTP 400.
- **Response**:
  ```json
  {
    "names": {"Display Name": "pubkey"},
    "relays": {"pubkey": ["wss://relay1", ...]}
  }
  ```

### 1. Fetch User Profile
- **Endpoint**: `/fetch-profile`
- **Method**: `POST`
- **Description**: Fetches user metadata (Kind=0) from Nostr relays.
- **Request Body**:
  ```json
  {"pubkey": "user_public_key"}
  ```
- **Response**:
  ```json
  {"id":"event_id","pubkey":"user_public_key",
   "content":{ "name":"username","nip05":"user@domain.com",
               "lud16":"lightning_address","website":"user_website",
               "about":"user_bio" }}
  ```

### 2. Fetch Metadata by Nprofile (NIP-19)
- **Endpoint**: `/fetch-nprofile`
- **Method**: `POST`
- **Description**: Decodes a Nostr `nprofile` string to derive the pubkey and relays, then retrieves metadata from those relays.
- **Request Body**:
  ```json
  {"nprofile": "nprofile_string"}
  ```
- **Response**:
  ```json
  {"pubkey": "hex_pubkey", "metadata": {...}}
  ```

### 3. Fetch Music Library
- **Endpoint**: `/tracks`
- **Method**: `GET`
- **Description**: Retrieves the aggregated music library from Wavlake.
  - Uses `SEARCH_TERM` to filter artists (default: " by Fuzzed Records").
  - The library is built on-demand if not cached so the first request returns data.
  - Subsequent requests return cached data immediately; stale caches refresh in the background.
  - Cache time-to-live is controlled by `TRACK_CACHE_TIMEOUT` (default: 300 seconds).
  - HTTP timeouts use `HTTP_TIMEOUT` (default: 5 seconds) to avoid long hangs.
- **Response**:
  ```json
  {"tracks":[
    {"artist":"artist_name","album":"album_title",
     "title":"track_title","media_url":"track_url",
     "track_id":"track_id"}
  ]}
  ```

### 4. Validate Profile (NIP-05)
- **Endpoint**: `/validate-profile`
- **Method**: `POST`
- **Description**: Confirms a public key’s NIP-05 identifier matches your domain.
- **Request Body**: `{ "pubkey":"user_pubkey" }`
- **Response**: `{"status":"valid"}` or `403` error

### 5. Send Ephemeral DM (NIP-17)
- **Endpoint**: `/send_dm`
- **Method**: `POST`
- **Description**: Encrypts and sends a direct message as Kind=23194. The
  message content is encrypted using NIP‑17's AES‑GCM flow with the sender's
  private key and recipient's public key. Ephemeral DMs are not persisted by
  relays.
- **Required Fields**: `pubkey`, `kind`, `created_at`, `tags=[['p',
  recipient_pubkey]]`, and encrypted `content`.
- **Request Body**:
  ```json
  {"to_pubkey":"...","content":"...",
   "sender_privkey":"..."}
  ```

### 6. Update Relays
- **Endpoint**: `/update-relays`
- **Method**: `POST`
- **Description**: Merges relay URLs into the active list and persists them to `relays.txt`.
- **Request Body**:
  ```json
  {"relays": ["wss://relay1", "wss://relay2"]}
  ```
- **Response**:
  ```json
  {"status":"updated","count":2}
  ```

---

## Workflow

1. **User Visits the Site**:
   - The homepage loads, displaying the music library.
   - Users can authenticate using their Nostr Wallet to view their profile.

2. **Authentication**:
   - Users click the "Profile" button and authenticate with their Nostr Wallet using NIP-07.
   - The backend fetches and validates their profile data.

3. **Music Library**:
   - Songs are fetched from Wavlake and displayed in the Library section.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **Nostr Protocol** for decentralized authentication.
- **Wavlake** for music streaming integration.
- **Microsoft Azure** for hosting the application.

---

For more information, visit [Fuzzed Records](https://fuzzedrecords.com).
