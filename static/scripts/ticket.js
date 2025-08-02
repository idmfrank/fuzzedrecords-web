// ticket.js
// Handles Lightning ticket purchase and receipt via ephemeral Nostr messages

const RELAYS = ['wss://relay.damus.io', 'wss://nos.lol'];

async function purchaseTicket(eventData) {
  try {
    const resp = await fetch('/generate-ticket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_id: eventData.id, pubkey: sessionStorage.getItem('pubkey') })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Failed to create invoice');
    if (!window.webln) {
      alert('Lightning wallet not available');
      return;
    }
    try {
      await window.webln.enable?.();
      await window.webln.sendPayment(data.invoice);
    } catch (err) {
      console.error('Payment failed', err);
      alert('Payment failed');
      return;
    }

    const confirmResp = await fetch('/confirm-payment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ invoice: data.invoice })
    });
    let confirmData = {};
    try {
      confirmData = await confirmResp.json();
    } catch (_) {}
    if (confirmResp.ok && confirmData.ticket) {
      displayTicket(confirmData.ticket);
      return;
    }
    alert('Payment sent. Awaiting ticket...');
  } catch (err) {
    console.error('Ticket generation failed', err);
    alert('Failed to generate ticket');
  }
}

function displayTicket(payload) {
  const qrContainer = document.getElementById('qr-code');
  if (qrContainer) {
    qrContainer.innerHTML = '';
    const img = document.createElement('img');
    img.src = payload.qr_code;
    img.alt = 'Ticket QR';
    qrContainer.appendChild(img);
    const info = document.createElement('p');
    info.textContent = payload.note || '';
    qrContainer.appendChild(info);
  }
  sessionStorage.setItem('ticket', JSON.stringify(payload));
}

function subscribeForTickets() {
  const pubkey = sessionStorage.getItem('pubkey');
  if (!pubkey || !window.nostr?.nip44?.decrypt) {
    setTimeout(subscribeForTickets, 1000);
    return;
  }
  RELAYS.forEach(url => {
    const ws = new WebSocket(url);
    ws.onopen = () => {
      ws.send(JSON.stringify(['REQ', 'ticket-sub', { kinds: [24133], '#p': [pubkey] }]));
    };
    ws.onmessage = async msg => {
      try {
        const data = JSON.parse(msg.data);
        if (data[0] === 'EVENT' && data[1] === 'ticket-sub') {
          const ev = data[2];
          const decrypted = await window.nostr.nip44.decrypt(ev.pubkey, ev.content);
          const payload = JSON.parse(decrypted);
          displayTicket(payload);
        }
      } catch (err) {
        console.error('Failed to process ticket event', err);
      }
    };
  });
}

document.addEventListener('click', async e => {
  if (e.target.classList.contains('generate-ticket-btn')) {
    const data = JSON.parse(e.target.getAttribute('data-event'));
    await purchaseTicket(data);
  }
});

document.addEventListener('DOMContentLoaded', () => {
  subscribeForTickets();
});
