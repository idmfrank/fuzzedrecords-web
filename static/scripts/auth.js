// auth.js
// Handles navigation and Nostr authentication (NIP-07) logic
import { showSection } from './utils.js';

// Global profile state
let userProfile = null;

// Display user profile details
export function displayProfile(profileData) {
  const profileContainer = document.getElementById('profile-container');
  profileContainer.innerHTML = '';
  const { pubkey } = profileData;
  const content = profileData.content || {};
  if (content.picture) {
    const img = document.createElement('img');
    img.src = content.picture;
    img.alt = content.name || 'Profile Picture';
    img.classList.add('profile-pic');
    profileContainer.appendChild(img);
  }
  const detailsTable = document.createElement('table');
  detailsTable.classList.add('profile-details');
  // Always show pubkey; then any other profile details
  const details = [
    { label: 'Pubkey', value: pubkey },
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
    localStorage.setItem('pubkey', pubkey);
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
    userProfile = profileData;
    displayProfile(profileData);
  } catch (err) {
    console.error('Authentication error:', err);
  }
}

// Initialization: menu buttons
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('menu-library')
    .addEventListener('click', () => showSection('library'));
  document.getElementById('menu-profile')
    .addEventListener('click', async () => {
      const btn = document.getElementById('menu-profile');
      btn.textContent = 'Signing in...';
      await authenticateWithNostr();
      btn.textContent = 'Profile';
      document.getElementById('menu-events').style.display = 'inline-block';
      showSection('profile');
    });
});

document.addEventListener('DOMContentLoaded', () => {
  const menuProfile = document.getElementById('menu-profile');
  menuProfile.addEventListener('click', async () => {
    if (!menuProfile.dataset.loggedIn) {
      menuProfile.textContent = 'Signing in...';
      await authenticateWithNostr();
      menuProfile.textContent = 'Profile';
      document.getElementById('menu-events').style.display = 'inline-block';
    }
    showSection('profile');
  });
});