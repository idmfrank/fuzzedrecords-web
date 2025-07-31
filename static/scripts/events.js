// events.js
// Handles events section: fetching, rendering, and admin event creation
import { showSection, getTagValue, isAdmin } from './utils.js';

// Fetch and display fuzzed events
export async function fetchFuzzedEvents() {
  const container = document.getElementById('events-section-content');
  const registerBtn = document.getElementById('register-btn');
  container.innerHTML = '';

  let data;
  const cached = sessionStorage.getItem('fuzzedEvents');
  if (cached) {
    try {
      data = { events: JSON.parse(cached) };
    } catch (err) {
      console.warn('Failed to parse cached events:', err);
      sessionStorage.removeItem('fuzzedEvents');
    }
  }

  if (!data) {
    try {
      const response = await fetch('/fuzzed_events');
      data = await response.json();
      if (response.ok) {
        sessionStorage.setItem('fuzzedEvents', JSON.stringify(data.events || []));
      }
    } catch (err) {
      console.error('Error fetching events:', err);
      if (registerBtn) registerBtn.style.display = 'none';
      container.innerHTML = '<p>Error loading events.</p>';
      return;
    }
  }

  if (data.events && data.events.length > 0) {
    if (registerBtn && sessionStorage.getItem('pubkey')) {
      registerBtn.style.display = 'inline-block';
    }
    const seen = new Set();
    data.events.forEach(ev => {
      if (seen.has(ev.id)) return;
      seen.add(ev.id);
      const el = document.createElement('div');
      el.classList.add('event-item');
      const start = getTagValue(ev.tags, 'starts');
      const end = getTagValue(ev.tags, 'ends');
      const price = getTagValue(ev.tags, 'price');
      const category = getTagValue(ev.tags, 'category');

      const header = document.createElement('h3');
      header.textContent = getTagValue(ev.tags, 'title');
      el.appendChild(header);

      const table = document.createElement('table');
      table.classList.add('profile-details');
      const fields = [
        { label: 'Summary', value: getTagValue(ev.tags, 'summary') },
        { label: 'Location', value: getTagValue(ev.tags, 'location') },
        { label: 'Starts', value: new Date(start).toLocaleString() },
        { label: 'Ends', value: new Date(end).toLocaleString() }
      ];
      if (price !== 'N/A') fields.push({ label: 'Price', value: `$${price}` });
      if (category !== 'N/A') fields.push({ label: 'Category', value: category });

      fields.forEach(f => {
        const row = document.createElement('tr');
        const l = document.createElement('td');
        l.textContent = f.label;
        const v = document.createElement('td');
        v.textContent = f.value;
        row.appendChild(l);
        row.appendChild(v);
        table.appendChild(row);
      });
      el.appendChild(table);

      if (ev.content) {
        const desc = document.createElement('p');
        desc.textContent = ev.content;
        el.appendChild(desc);
      }
      if (ev.relay) {
        const relay = document.createElement('p');
        relay.classList.add('event-relay');
        relay.innerHTML = `<strong>Relay:</strong> ${ev.relay}`;
        el.appendChild(relay);
      }

      const btn = document.createElement('button');
      btn.classList.add('generate-ticket-btn');
      btn.dataset.event = JSON.stringify(ev);
      btn.textContent = 'Generate Ticket';
      el.appendChild(btn);

      container.appendChild(el);
    });
  } else {
    if (registerBtn) registerBtn.style.display = 'none';
    container.innerHTML = '<p>No events available.</p>';
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
    pubkey: sessionStorage.getItem('pubkey')
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
    if (sessionStorage.getItem('pubkey')) {
      fetchFuzzedEvents();
      showSection('events');
    } else {
      alert('Please sign in with Nostr to view events.');
    }
  });
  btnAdmin?.addEventListener('click', () => {
    if (isAdmin()) {
      showSection('admin');
    }
  });
  document.getElementById('event-form')?.addEventListener('submit', createEvent);
});