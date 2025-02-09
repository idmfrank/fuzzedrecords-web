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
- **User Profiles**: Authenticate using Nostr Wallet to view and manage your profile.
- **Admin Panel**: Create and publish events (restricted to verified admins).
- **Decentralized Authentication**: Uses Nostr Wallet for secure, decentralized user authentication.
- **Responsive Design**: Optimized for both desktop and mobile devices.
- **QR Code Generation**: Generate QR codes for quick sharing and access (e.g., profile links).
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
  - NIP-05 verification for admin access
- **Hosting**:
  - Microsoft Azure
  - Gunicorn as WSGI server

---

## File Structure

```
fuzzedrecords/
├── templates/index.html      # Main HTML file for the website
├── static/scripts/profile.js # JavaScript for user interactions and authentication
├── static/style.css          # CSS for styling the website
├── app.py                    # Flask backend for API and logic
├── requirements.txt          # Python dependencies
├── startup.sh                # Deployment script for Azure
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

4. **Run the Application Locally**:
   ```bash
   python app.py
   ```

5. **Deploy to Azure**:
   - Ensure `startup.sh` is executable:
     ```bash
     chmod +x startup.sh
     ```
   - Deploy the app to Azure WebApp using the Azure CLI or portal.

---

## API Endpoints

### **1. Fetch User Profile**
- **Endpoint**: `/fetch-profile`
- **Method**: `POST`
- **Description**: Fetches user profile data from Nostr relays.
- **Request Body**:
  ```json
  {
    "pubkey": "user_public_key"
  }
  ```
- **Response**:
  ```json
  {
    "id": "event_id",
    "pubkey": "user_public_key",
    "content": {
      "name": "username",
      "nip05": "user@domain.com",
      "lud16": "lightning_address",
      "website": "user_website",
      "about": "user_bio"
    },
    "sig": "event_signature"
  }
  ```

### **2. Fetch Music Library**
- **Endpoint**: `/tracks`
- **Method**: `GET`
- **Description**: Fetches the music library from Wavlake.
- **Response**:
  ```json
  {
    "tracks": [
      {
        "artist": "artist_name",
        "album": "album_title",
        "title": "track_title",
        "media_url": "track_url",
        "track_id": "track_id"
      }
    ]
  }
  ```

### **3. Create Event (Admin-Only)**
- **Endpoint**: `/create_event`
- **Method**: `POST`
- **Description**: Creates and publishes an event to Nostr relays.
- **Request Body**:
  ```json
  {
    "title": "event_title",
    "venue": "event_venue",
    "date": "event_date",
    "price": "event_price",
    "description": "event_description",
    "pubkey": "admin_public_key",
    "sig": "event_signature"
  }
  ```
- **Response**:
  ```json
  {
    "message": "Event created successfully",
    "event_id": "event_id"
  }
  ```

---

## Workflow

1. **User Visits the Site**:
   - The homepage loads, displaying the music library.
   - Users can authenticate using their Nostr Wallet to view their profile.

2. **Authentication**:
   - Users click the "Profile" button and authenticate with their Nostr Wallet.
   - The backend fetches and validates their profile data.

3. **Admin Actions**:
   - Verified admins can access the Admin section and create events.
   - Events are published to Nostr relays.

4. **Music Library**:
   - Songs are fetched from Wavlake and displayed in the Library section.

5. **QR Code and Messaging**:
   - QR codes can be generated for quick sharing or profile access.
   - Admins can send direct messages, enhancing communication.

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