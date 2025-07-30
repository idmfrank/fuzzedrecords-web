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
        const start = getTagValue(ev.tags, 'starts');
        const end = getTagValue(ev.tags, 'ends');
        const price = getTagValue(ev.tags, 'price');
        const category = getTagValue(ev.tags, 'category');
        el.innerHTML = `
          <h3>${getTagValue(ev.tags, 'title')}</h3>
          <p><strong>Summary:</strong> ${getTagValue(ev.tags, 'summary')}</p>
          <p><strong>Location:</strong> ${getTagValue(ev.tags, 'location')}</p>
          <p><strong>Starts:</strong> ${new Date(start).toLocaleString()}</p>
          <p><strong>Ends:</strong> ${new Date(end).toLocaleString()}</p>
        `;
        if (price !== 'N/A') {
          el.innerHTML += `<p><strong>Price:</strong> $${price}</p>`;
        }
        if (category !== 'N/A') {
          el.innerHTML += `<p><strong>Category:</strong> ${category}</p>`;
        }
        el.innerHTML += `<p>${ev.content}</p>`;
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
    summary: data.get('event-summary'),
    location: data.get('event-location'),
    starts: data.get('event-start'),
    ends: data.get('event-end'),
    price: data.get('event-price'),
    category: data.get('event-category'),
    description: data.get('event-description'),
    pubkey: localStorage.getItem('pubkey')
  };
  try {
    if (!window.nostr) throw new Error('Nostr wallet not available');
    const tags = [
      ['d', crypto.randomUUID()],
      ['title', eventData.title],
      ['summary', eventData.summary],
      ['location', eventData.location],
      ['starts', eventData.starts],
      ['ends', eventData.ends]
    ];
    if (eventData.price) tags.push(['price', String(eventData.price)]);
    if (eventData.category) tags.push(['category', eventData.category]);
    const template = {
      // NIP-52 calendar event kind
      kind: 31922,
      created_at: Math.floor(Date.now()/1000),
      tags,
      content: eventData.description,
      pubkey: eventData.pubkey
    };
    const signed = await window.nostr.signEvent(template);
    const resp = await fetch('/create_event', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(signed)
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