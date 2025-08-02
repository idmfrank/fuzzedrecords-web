# User Story: Event Ticketing via Lightning & Ephemeral Nostr Messaging

**Title**:  
Pancho Registers for an Event and Receives a Ticket via Ephemeral Encrypted Nostr Message

**Epic**:  
Event Registration and Ticketing (Fuzzed Records)

**Priority**:  
High

**Tags**:  
Nostr, NIP-17, NIP-44, Lightning, Alby, WebLN, Ticketing, Ephemeral Messaging

---

## As a  
Nostr-authenticated user (e.g., Pancho)

## I want to  
Register for an event and pay using my Lightning wallet (Alby), and receive my ticket as an ephemeral encrypted message (NIP-17) via a Nostr relay

## So that  
My ticket is delivered securely, privately, and in real-time without persistent storage on relays

---

## Acceptance Criteria

1. **User Authentication**
   - [x] User signs in using a Nostr wallet (e.g., Alby)
   - [x] Their public key (npub) is cached and available in the session or frontend memory
   - [x] UI updates to show available events and “Generate Ticket” buttons

2. **Lightning Payment via WebLN**
   - [x] Clicking “Generate Ticket” triggers a POST request to `/generate-ticket`
   - [x] The backend creates a Lightning invoice (e.g., via LNbits)
   - [x] The frontend calls `window.webln.sendPayment(invoice)` to pay
   - [x] On successful payment, the app sends a confirmation to `/confirm-payment`

3. **Ephemeral Ticket Delivery via NIP-17**
   - [x] Server prepares a ticket payload:
     ```json
     {
       "ticket_id": "ticket_abc123",
       "event_id": "event_xyz789",
       "qr_code": "https://fuzzedrecords.com/tickets/abc123.png",
       "note": "Thanks Pancho, here’s your ticket!"
     }
     ```
   - [x] Payload is encrypted using NIP-44 (XChaCha20-Poly1305)
   - [x] Encrypted payload is sent as a `kind=24133` Nostr event
   - [x] Event includes `["p", user_npub]` tag and is signed with server’s key
   - [x] Event is broadcast to all supported relays (e.g., `relay.damus.io`, `nos.lol`)

4. **Client-Side Ticket Receipt**
   - [x] Frontend polls subscribed relays for `kind=24133` events
   - [x] If a matching event (tagged for the user) is found, it is decrypted using NIP-44
   - [x] Ticket is displayed in the browser (QR code + event info)
   - [x] Optionally: Event stored locally in browser session for reuse

---

## Technical Details

- **Event Kind**: `24133` (Ephemeral Encrypted Message)
- **Encryption**: NIP-44 using sender `nsec` and receiver `npub`
- **Frontend**: `ticket.js`, `auth.js`, `events.js`
- **Backend**: `app.py` endpoints
  - `/generate-ticket`
  - `/confirm-payment`
  - `/send-ephemeral-ticket`
- **WebLN**: Use `window.webln.sendPayment(invoice)`
- **Relay Subscriptions**: Add support to subscribe for `kind=24133` with `["p", user_npub]`

---

## Out-of-Scope (for this story)

- Ticket resending or backup fallback (e.g., Kind 4 or email)
- Multi-user ticket transfers
- Advanced wallet support beyond Alby

---

**Status**: Completed

**Ready for Testing**: Yes
