// events.js
// Handles events section: fetching, rendering, and admin event creation
import { showSection, getTagValue } from './utils.js';

// Fetch and display fuzzed events
export async function fetchFuzzedEvents() {
  const container = document.getElementById('events-section-content');
  const registerBtn = document.getElementById('register-btn');
  container.innerHTML = '';
  try {
    const response = await fetch('/fuzzed_events');
    const data = await response.json();
    if (data.events && data.events.length > 0) {
      if (registerBtn && localStorage.getItem('pubkey')) {
        registerBtn.style.display = 'inline-block';
      }
      data.events.forEach(ev => {
        const el = document.createElement('div');
        el.classList.add('event-item');
        el.innerHTML = `
          <h3>${getTagValue(ev.tags, 'title')}</h3>
          <p><strong>Venue:</strong> ${getTagValue(ev.tags, 'venue')}</p>
          <p><strong>Date:</strong> ${new Date(getTagValue(ev.tags, 'date')).toLocaleString()}</p>
          <p><strong>Fee:</strong> $${getTagValue(ev.tags, 'fee')}</p>
          <p>${ev.content}</p>
        `;
        el.innerHTML += `<button class="generate-ticket-btn" data-event='${JSON.stringify(ev)}'>Generate Ticket</button>`;
        container.appendChild(el);
      });
    } else {
      if (registerBtn) registerBtn.style.display = 'none';
      container.innerHTML = '<p>No events available.</p>';
    }
  } catch (err) {
    console.error('Error fetching events:', err);
    if (registerBtn) registerBtn.style.display = 'none';
    container.innerHTML = '<p>Error loading events.</p>';
  }
}

// Handle admin event creation
export async function createEvent(e) {
  e.preventDefault();
  const form = e.target;
  const data = new FormData(form);
  const eventData = {
    title: data.get('event-title'),
    venue: data.get('event-venue'),
    date: data.get('event-date'),
    fee: data.get('event-fee'),
    description: data.get('event-description'),
    pubkey: localStorage.getItem('pubkey')
  };
  try {
    if (!window.nostr) throw new Error('Nostr wallet not available');
    const template = {
      kind: 31922,
      created_at: Math.floor(Date.now()/1000),
      tags: [
        ['title', eventData.title],
        ['venue', eventData.venue],
        ['date', eventData.date],
        ['fee', String(eventData.fee)]
      ],
      content: eventData.description,
      pubkey: eventData.pubkey
    };
    const signed = await window.nostr.signEvent(template);
    const resp = await fetch('/create_event', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({...template, sig: signed.sig})
    });
    if (!resp.ok) throw new Error((await resp.json()).error || 'Unknown');
    alert('Event created successfully!');
    form.reset();
  } catch (err) {
    console.error('Error creating event:', err);
    alert('Failed to create event: ' + err.message);
  }
}

// Initialize events UI
document.addEventListener('DOMContentLoaded', () => {
  const btnEvents = document.getElementById('menu-events');
  const btnAdmin = document.getElementById('menu-admin');
  btnEvents?.addEventListener('click', () => {
    if (localStorage.getItem('pubkey')) {
      fetchFuzzedEvents();
      showSection('events');
    } else {
      alert('Please sign in with Nostr to view events.');
    }
  });
  btnAdmin?.addEventListener('click', () => showSection('admin'));
  document.getElementById('event-form')?.addEventListener('submit', createEvent);
});