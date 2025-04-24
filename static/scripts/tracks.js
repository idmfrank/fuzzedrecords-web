// tracks.js
// Handles fetching and rendering the music library
import { fetchTracks } from './profile.js';

document.addEventListener('DOMContentLoaded', () => {
  fetchTracks();
});