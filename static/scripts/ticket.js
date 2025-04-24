// ticket.js
// Handles ticket generation, QR display, and sending via DM
import { generateTicketWithQRCode } from './profile.js';

document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', async (e) => {
    if (e.target.classList.contains('generate-ticket-btn')) {
      const eventData = JSON.parse(e.target.getAttribute('data-event'));
      await generateTicketWithQRCode(eventData);
    }
  });
});