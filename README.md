**Fuzzed Records** website is a music-related platform hosted on Microsoft Azure. The site integrates with **Wavlake** for music distribution and uses **Nostr Wallet Connect** for decentralized authentication. Below is a detailed breakdown of the components, methods, and functionality:

---

### **1. Overview of the Website**
- **Purpose**: Fuzzed Records is a music platform that allows users to explore a library of songs, manage their profiles, and (for admins) create events. It leverages decentralized technologies for authentication and integrates with Wavlake for music streaming.
- **Key Features**:
  - **Music Library**: Displays songs hosted on Wavlake.
  - **User Profiles**: Requires authentication via Nostr Wallet to display profile details.
  - **Admin Panel**: Allows admins to create events (restricted to users with verified NIP-05 domains).
  - **Decentralized Authentication**: Uses Nostr Wallet Connect for user authentication and profile management.

---

### **2. File Breakdown**

#### **a. `index.html`**
- **Structure**: The main HTML file for the website.
- **Key Sections**:
  - **Header**: Displays the Fuzzed Records logo.
  - **Navigation Menu**: Buttons for Library, Profile, and Admin sections.
  - **Library Section**: Displays songs from Wavlake using embedded iframes.
  - **Profile Section**: Shows user profile details after Nostr Wallet authentication.
  - **Admin Section**: A form for admins to create events (visible only to verified users).
- **Dynamic Content**:
  - Songs are loaded dynamically via JavaScript.
  - Profile details are fetched after Nostr Wallet Connect authentication.

#### **b. `profile.js`**
- **Functionality**: Handles user interactions, authentication, and dynamic content loading.
- **Key Methods**:
  - **`authenticateWithNostr()`**: Authenticates users using Nostr Wallet and fetches their profile data.
  - **`displayProfile(profileData)`**: Displays user profile details (e.g., username, NIP-05, LUD-16, etc.).
  - **`createEvent(eventData)`**: Submits event data to the server for creation (admin-only).
  - **`fetch("/tracks")`**: Fetches and displays songs from the Wavlake API.
  - **`showSection(section)`**: Toggles visibility of sections (Library, Profile, Admin).

#### **c. `style.css`**
- **Design**: Provides a clean, responsive design with a dark theme for the menu and light theme for content sections.
- **Key Features**:
  - Responsive layout for mobile and desktop.
  - Styled buttons, forms, and profile details.
  - Embedded Wavlake player styling.

#### **d. `app.py`**
- **Backend**: A Flask application that handles API requests, authentication, and event creation.
- **Key Routes**:
  - **`/fetch-profile`**: Fetches user profile data from Nostr relays.
  - **`/tracks`**: Fetches and returns the music library from Wavlake.
  - **`/create_event`**: Creates an event (admin-only, requires NIP-05 verification).
  - **`/validate-profile`**: Validates user profiles against the required domain (`fuzzedrecords.com`).
- **Helper Methods**:
  - **`fetch_and_validate_profile(pubkey, required_domain)`**: Validates user profiles using NIP-05.
  - **`build_music_library()`**: Fetches artists, albums, and tracks from Wavlake to build the music library.
  - **`fetch_artists()`**, **`fetch_albums()`**, **`fetch_tracks()`**: Fetch data from the Wavlake API.

#### **e. `requirements.txt`**
- **Dependencies**: Lists Python packages required for the application:
  - Flask, Flask-RESTful, flask-cors, pynostr, requests, msal.

#### **f. `startup.sh`**
- **Deployment Script**: Sets up the environment and starts the Flask app using Gunicorn.
- **Steps**:
  - Creates a virtual environment.
  - Installs dependencies from `requirements.txt`.
  - Starts the app on port 8000.

---

### **3. Key Technologies and Methods**

#### **a. Nostr Wallet Integration**
- **Purpose**: Decentralized authentication and profile management.
- **How It Works**:
  - Users authenticate using their Nostr Wallet, which provides a public key (`pubkey`).
  - The backend fetches profile data from Nostr relays using the `pubkey`.
  - Profiles are validated using NIP-05 to ensure they belong to the `fuzzedrecords.com` domain.

#### **b. Wavlake Integration**
- **Purpose**: Hosts and streams music content.
- **How It Works**:
  - The backend fetches artists, albums, and tracks from the Wavlake API.
  - Songs are displayed in the frontend using embedded Wavlake iframes.

#### **c. Event Creation (Admin-Only)**
- **Purpose**: Allows admins to create events.
- **How It Works**:
  - Admins submit event details via a form.
  - The backend validates the admin's NIP-05 domain and publishes the event to Nostr relays.

#### **d. Caching**
- **Purpose**: Improves performance by caching profile data.
- **How It Works**:
  - Profile data is cached in memory for a configurable timeout (`CACHE_TIMEOUT`).

#### **e. Microsoft Azure Integration**
- **Purpose**: Hosts the web application.
- **How It Works**:
  - The app is deployed as a WebApp using Gunicorn as the WSGI server.
  - The `startup.sh` script handles environment setup and app startup.

---

### **4. Workflow**

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

---

### **5. Summary**
Fuzzed Records is a modern music platform that combines decentralized authentication (Nostr Wallet) with music streaming (Wavlake). The site is built using Flask for the backend, with a responsive frontend and dynamic content loading. Key features include:
- Decentralized user profiles.
- Integration with Wavlake for music distribution.
- Admin-only event creation with NIP-05 verification.
- Hosted on Microsoft Azure with Gunicorn for production deployment.

This setup reflects a growing trend in the music industry toward decentralized technologies and user-centric platforms.