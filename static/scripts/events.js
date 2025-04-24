// events.js
// Handles events section: fetching, rendering, and admin event creation
import { showSection } from './profile.js';
import { fetchFuzzedEvents, createEvent } from './profile.js';

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('menu-events')
    .addEventListener('click', () => showSection('events'));
  document.getElementById('menu-admin')
    .addEventListener('click', () => showSection('admin'));
  // Fetch and render events on load
  fetchFuzzedEvents();
  // Attach admin form submission
  const eventForm = document.getElementById('event-form');
  if (eventForm) {
    eventForm.addEventListener('submit', createEvent);
  }
});