// auth.js
// Handles navigation and Nostr authentication (NIP-07) logic
import { showSection, displayProfile, fetchFuzzedEvents } from './profile.js';
import { authenticateWithNostr } from './profile.js';

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