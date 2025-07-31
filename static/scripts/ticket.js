// ticket.js
// Handles ticket generation, QR display, and sending via Nostr Wallet Connect
import { getTagValue } from './utils.js';

// Server wallet pubkey should be exposed on the window object
const SERVER_WALLET_PUBKEY = window.serverWalletPubkey || '';

// Generate ticket payload, display QR, and send DM
export async function generateTicketWithQRCode(eventData) {
  const ticketId = crypto.randomUUID();
  const eventId = eventData.id;
  const eventName = getTagValue(eventData.tags, 'title');
  const ticketData = {
    ticket_id: ticketId,
    event_id: eventId,
    pubkey: sessionStorage.getItem('pubkey'),
    event_name: eventName
  };
  const qrContainer = document.getElementById('qr-code');
  if (qrContainer) {
    qrContainer.innerHTML = '';
    new QRCode(qrContainer, { text: JSON.stringify(ticketData), width: 256, height: 256 });
  }
  await sendTicketViaNostrRequest(ticketData);
}

// Encrypt and send ticket via NIP-47 wallet request
async function sendTicketViaNostrRequest(ticketData) {
  if (!window.nostr) {
    console.error('Nostr wallet not available.');
    return;
  }
  const payload = {
    method: 'ticket.create',
    params: ticketData,
    id: crypto.randomUUID()
  };
  const content = JSON.stringify(payload);
  try {
    let encrypted = content;
    if (window.nostr.nip44?.encrypt) {
      encrypted = await window.nostr.nip44.encrypt(SERVER_WALLET_PUBKEY, content);
    } else if (window.nostr.nip04?.encrypt) {
      encrypted = await window.nostr.nip04.encrypt(SERVER_WALLET_PUBKEY, content);
    }
    const reqEvent = {
      kind: 23194,
      created_at: Math.floor(Date.now() / 1000),
      tags: [['p', SERVER_WALLET_PUBKEY]],
      content: encrypted,
      pubkey: sessionStorage.getItem('pubkey')
    };
    const signed = await window.nostr.signEvent(reqEvent);
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
    console.error('Error sending ticket request:', err);
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