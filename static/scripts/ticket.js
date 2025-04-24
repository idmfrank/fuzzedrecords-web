// ticket.js
// Handles ticket generation, QR display, and sending via Nostr DM
import { getTagValue } from './utils.js';

// Generate ticket payload, display QR, and send DM
export async function generateTicketWithQRCode(eventData) {
  const ticketId = crypto.randomUUID();
  const eventId = eventData.id;
  const eventName = getTagValue(eventData.tags, 'title');
  const ticketData = {
    ticket_id: ticketId,
    event_id: eventId,
    pubkey: localStorage.getItem('pubkey'),
    event_name: eventName
  };
  const qrContainer = document.getElementById('qr-code');
  if (qrContainer) {
    qrContainer.innerHTML = '';
    new QRCode(qrContainer, { text: JSON.stringify(ticketData), width: 256, height: 256 });
  }
  await sendTicketViaNostrDM(ticketData);
}

// Encrypt and send ticket via kind=4 Nostr event
async function sendTicketViaNostrDM(ticketData) {
  if (!window.nostr) {
    console.error('Nostr wallet not available.');
    return;
  }
  const content = JSON.stringify(ticketData);
  try {
    let encrypted = content;
    if (window.nostr.nip44?.encrypt) {
      encrypted = await window.nostr.nip44.encrypt(ticketData.pubkey, content);
    }
    const dmEvent = {
      kind: 4,
      created_at: Math.floor(Date.now() / 1000),
      tags: [['p', ticketData.pubkey]],
      content: encrypted,
      pubkey: localStorage.getItem('pubkey')
    };
    const signed = await window.nostr.signEvent(dmEvent);
    const resp = await fetch('/send_ticket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(signed)
    });
    const result = await resp.json();
    if (result.status === 'sent') {
      alert('Success! Check your Nostr DMs for your event ticket.');
    } else {
      alert('Failed to send ticket. Please try again.');
    }
  } catch (err) {
    console.error('Error sending ticket DM:', err);
    alert('Error sending ticket.');
  }
}

// Attach click handler for ticket buttons
document.addEventListener('click', async e => {
  if (e.target.classList.contains('generate-ticket-btn')) {
    const data = JSON.parse(e.target.getAttribute('data-event'));
    await generateTicketWithQRCode(data);
  }
});