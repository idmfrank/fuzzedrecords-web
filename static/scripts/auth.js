// auth.js
// Handles navigation and Nostr authentication (NIP-07) logic
import { showSection, isAdmin } from './utils.js';

// Global profile state
let userProfile = null;

function renderProfileWhenReady(profileData) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => displayProfile(profileData), { once: true });
  } else {
    displayProfile(profileData);
  }
}

async function validateProfile(pubkey) {
  try {
    const resp = await fetch('/validate-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pubkey })
    });
    return resp.ok;
  } catch (err) {
    console.error('Validation error:', err);
    return false;
  }
}

// Display user profile details
export function displayProfile(profileData) {
  const profileContainer = document.getElementById('profile-container');
  if (!profileContainer) {
    console.error('profile-container element not found');
    return;
  }
  profileContainer.innerHTML = '';
  const { pubkey } = profileData;
  const content = profileData.content || {};
  if (Object.keys(content).length === 0) {
    const msg = document.createElement('p');
    msg.classList.add('empty-profile');
    msg.textContent = 'No Nostr profile found for this public key. Please check your wallet or try again.';
    profileContainer.appendChild(msg);
  }
  if (content.picture) {
    const img = document.createElement('img');
    img.src = content.picture;
    img.alt = content.name || 'Profile Picture';
    img.classList.add('profile-pic');
    profileContainer.appendChild(img);
  }
  const detailsTable = document.createElement('table');
  detailsTable.classList.add('profile-details');
  // Display profile fields other than nprofile/npub
  const details = [
    { label: 'Username', value: content.name },
    { label: 'NIP-05', value: content.nip05 },
    { label: 'LUD-16', value: content.lud16 },
    { label: 'Website', value: content.website },
    { label: 'About', value: content.about }
  ];
  details.forEach(d => {
    if (d.value) {
      const row = document.createElement('tr');
      const labelCell = document.createElement('td');
      labelCell.textContent = d.label;
      const valueCell = document.createElement('td');
      if (d.label === 'NIP-05' && d.value.includes('@')) {
        const [name, domain] = d.value.split('@');
        const link = document.createElement('a');
        link.href = `https://${domain}/.well-known/nostr.json?name=${name}`;
        link.textContent = d.value;
        valueCell.appendChild(link);
      } else {
        valueCell.textContent = d.value;
      }
      row.appendChild(labelCell);
      row.appendChild(valueCell);
      detailsTable.appendChild(row);
    }
  });
  profileContainer.appendChild(detailsTable);
}

// Authenticate with Nostr via NIP-07
export async function authenticateWithNostr() {
  if (!window.nostr) {
    console.error('NOSTR wallet not available.');
    return;
  }
  try {
    const pubkey = await window.nostr.getPublicKey();
    console.log('Retrieved pubkey:', pubkey);
    sessionStorage.setItem('pubkey', pubkey);
    console.log('Fetching profile for', pubkey);
    const response = await fetch('/fetch-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pubkey })
    });
    let profileData = await response.json();
    // If error or not ok, fallback to showing pubkey only
    if (!response.ok || profileData.error) {
      console.warn('fetch-profile error:', profileData.error);
      profileData = { pubkey };
    }
    if (!profileData.content) {
      console.warn('No profile data returned for', pubkey);
    }
    userProfile = profileData;
    renderProfileWhenReady(profileData);
  const adminStatus = await validateProfile(pubkey);
  sessionStorage.setItem('isAdmin', adminStatus ? 'true' : 'false');
  const adminBtn = document.getElementById('menu-admin');
  if (adminBtn) {
    adminBtn.style.display = adminStatus ? 'inline-block' : 'none';
  }
  if (window.nostr.getRelays) {
      try {
        const info = await window.nostr.getRelays();
        const relays = Object.keys(info || {});
        if (relays.length) {
          await fetch('/update-relays', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ relays })
          });
        }
      } catch (err) {
        console.warn('getRelays failed:', err);
      }
    }
  } catch (err) {
    console.error('Authentication error:', err);
  }
}

// Initialization: menu buttons
document.addEventListener('DOMContentLoaded', () => {
  // Clear session data so admin UI requires fresh login each reload
  sessionStorage.removeItem('pubkey');
  sessionStorage.removeItem('isAdmin');
  document.getElementById('menu-library')
    .addEventListener('click', () => showSection('library'));
  document.getElementById('menu-gear')
    .addEventListener('click', () => showSection('gear'));
  const menuProfile = document.getElementById('menu-profile');
  menuProfile.addEventListener('click', async () => {
    if (!menuProfile.dataset.loggedIn) {
      menuProfile.textContent = 'Signing in...';
      await authenticateWithNostr();
      menuProfile.textContent = 'Profile';
      document.getElementById('menu-events').style.display = 'inline-block';
      menuProfile.dataset.loggedIn = 'true';
    }
    showSection('profile');
  });

  // Allow linking directly to a section via URL hash (e.g., /#gear)
  const hash = window.location.hash.replace('#', '');
  const sections = ['library', 'profile', 'events', 'admin', 'gear'];
  if (sections.includes(hash)) {
    showSection(hash);
  }

  const adminBtn = document.getElementById('menu-admin');
  if (adminBtn) {
    adminBtn.style.display = isAdmin() ? 'inline-block' : 'none';
  }
});
