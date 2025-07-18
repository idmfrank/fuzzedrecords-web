# Fuzzed Records

Fuzzed Records is a modern music platform that integrates decentralized authentication with music streaming. It allows users to explore a library of songs, manage their profiles, and (for admins) create events. The platform leverages **Nostr Wallet** for decentralized authentication and **Wavlake** for music distribution by Fuzzed Records.

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
- **Admin Panel**: Create and publish events (restricted to verified admins).
- **Decentralized Authentication**: Uses Nostr Wallet for secure, decentralized user authentication.
- **Responsive Design**: Optimized for both desktop and mobile devices.
- **QR Code Ticketing**: Generate QR code tickets for live music events, sent via Nostr DM to users.
- **Efficient Data Caching**: Utilizes caching for optimizing data retrieval performance.

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
  - Gunicorn as WSGI server

---

## Configuration

Set the following environment variables to configure the application:

- RELAY_URLS: Comma-separated list of Nostr relay URLs (default: wss://relay.damus.io,wss://relay.primal.net,wss://relay.mostr.pub)
- CACHE_TIMEOUT: Seconds to cache fetched user profiles (default: 300)
- REQUIRED_DOMAIN: Domain for NIP-05 profile verification (default: fuzzedrecords.com)
 - WAVLAKE_API_BASE: Base URL for Wavlake API (default: https://wavlake.com/api/v1)
 - HTTP_TIMEOUT: Timeout in seconds for each Wavlake API request (default: 5)
 - TRACK_CACHE_TIMEOUT: Seconds to cache the music library before background refresh (default: 300)
 - SEARCH_TERM: Search term used to filter Wavlake artists (default: " by Fuzzed Records")
- TENANT_ID: Azure AD Tenant ID for discovery JSON endpoint (/.well-known/nostr.json)
- CLIENT_ID: Azure AD Application (client) ID
- CLIENT_SECRET: Azure AD Application client secret
- (Optional) LOG_LEVEL: Python log level for application logging (default: DEBUG)

---

## File Structure

```
./
├── app.py                    # Top-level Flask router (imports modular routes)
├── azure_resources.py        # MSAL & Nostr discovery JSON endpoint
├── nostr_utils.py            # Nostr endpoints: /fetch-profile, /validate-profile, events
├── wavlake_utils.py          # Wavlake API helpers and /tracks endpoint
├── ticket_utils.py           # Ticket generation & /send_ticket endpoint
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
        ├── events.js         # Frontend events & admin form logic
        ├── ticket.js         # Frontend ticket generation & DM logic
        └── utils.js          # Shared JavaScript helper functions
```

---

## Setup and Deployment

### Prerequisites
- Python 3.x
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
   python3 -m venv antenv
   source antenv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   > **Note**: `static/style.css` is committed; no Sass/SCSS compilation is required.

4. **Run the Application Locally**:
   ```bash
   python app.py
   ```

5. **Deploy to Azure**:
   - Ensure `startup.sh` is executable:
     ```bash
     chmod +x startup.sh
     ```
   - `startup.sh` installs Python dependencies and then launches the server.
   - Deploy the app to Azure WebApp using the Azure CLI or portal.
    > **Note**: The application must be able to establish outbound WebSocket connections to the relays listed in `RELAY_URLS`. Blocked outbound traffic will result in profile fetch failures.

---

## API Endpoints

### 0. Nostr Discovery JSON
- **Endpoint**: `/.well-known/nostr.json`
- **Method**: `GET`
- **Description**: Returns a Nostr discovery document containing admin user public keys and their associated relay URLs, sourced from Azure AD groups.
- **Response**:
  ```json
  {
    "names": {"Display Name": "pubkey", ...},
    "relays": {"pubkey": ["wss://relay1", ...], ...}
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

### 2. Fetch Music Library
- **Endpoint**: `/tracks`
- **Method**: `GET`
- **Description**: Retrieves the aggregated music library from Wavlake.
  - Uses `SEARCH_TERM` to filter artists (default: " by Fuzzed Records").
  - The first request returns an empty list and starts a background fetch of data.
  - Subsequent requests return cached data immediately (fresh or stale).
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

### 3. Create Event (Admin Only)
- **Endpoint**: `/create_event`
- **Method**: `POST`
- **Description**: Publishes a signed Kind=1 (text note) or custom event to relays.
- **Request Body**:
  ```json
  {"pubkey":"...","sig":"...","kind":1,"created_at":timestamp,
   "tags":[["title","event_title"],...],"content":"event_description"}
  ```
- **Response**:
  ```json
  {"message":"Event successfully broadcasted"}
  ```

### 4. Validate Profile (NIP-05)
- **Endpoint**: `/validate-profile`
- **Method**: `POST`
- **Description**: Confirms a public key’s NIP-05 identifier matches your domain.
- **Request Body**: `{ "pubkey":"user_pubkey" }`
- **Response**: `{"status":"valid"}` or `403` error

### 5. Fetch Fuzzed Events
- **Endpoint**: `/fuzzed_events`
- **Method**: `GET`
- **Description**: Retrieves Kind=52 events from verified accounts.
- **Response**:
  ```json
  {"events":[{"id":"...","pubkey":"...",
               "content":"...","tags":[],"created_at":...},...]} 
  ```

### 6. Send Encrypted DM (NIP-04)
- **Endpoint**: `/send_dm`
- **Method**: `POST`
- **Description**: Encrypts and sends a direct message as Kind=4.
- **Request Body**:
  ```json
  {"to_pubkey":"...","content":"...",
   "sender_privkey":"..."}
  ```

### 7. Send Ticket via DM
- **Endpoint**: `/send_ticket`
- **Method**: `POST`
- **Description**: Encrypts a ticket payload and sends a ticket DM.
- **Request Body**:
  ```json
  {"event_name":"...","recipient_pubkey":"...",
   "sender_privkey":"...","timestamp":...}
  ```
- **Response**:
  ```json
  {"status":"sent","event_id":"..."}
  ```

---

## Workflow

1. **User Visits the Site**:
   - The homepage loads, displaying the music library.
   - Users can authenticate using their Nostr Wallet to view their profile.

2. **Authentication**:
   - Users click the "Profile" button and authenticate with their Nostr Wallet using NIP-07.
   - The backend fetches and validates their profile data.

3. **Admin Actions**:
   - Verified admins can access the Admin section and create events.
   - Events are published to Nostr relays.

4. **Music Library**:
   - Songs are fetched from Wavlake and displayed in the Library section.

5. **QR Code and Messaging**:
   - QR code tickets for events are generated and sent via Nostr DM to users.

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
