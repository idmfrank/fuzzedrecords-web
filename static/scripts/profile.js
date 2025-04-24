document.addEventListener('DOMContentLoaded', function () {

    // Menu elements
    const menuLibrary = document.getElementById('menu-library');
    const menuProfile = document.getElementById('menu-profile');
    const menuEvents = document.getElementById('menu-events');
    const menuAdmin = document.getElementById('menu-admin');
  
    // Section elements
    const librarySection = document.getElementById('library-section');
    const profileSection = document.getElementById('profile-section');
    const eventsSection = document.getElementById('events-section');
    const adminSection = document.getElementById('admin-section');
  
    // Other elements
    const eventForm = document.getElementById('event-form');
    const qrContainer = document.getElementById('qr-code');
  
    // Set default view: show library; Profile button initially reads "Nostr Login"
    showSection('library');
    menuProfile.textContent = "Nostr Login";
  
    // Event Listeners for Menu Buttons
    menuLibrary.addEventListener('click', () => showSection('library'));
  
    menuProfile.addEventListener('click', async () => {
      if (!userProfile) {
        menuProfile.textContent = "Signing in...";
        await authenticateWithNostr();
        if (userProfile) {
          menuProfile.textContent = "Profile";
          // After successful login, also show the Events button
          menuEvents.style.display = "inline-block";
        } else {
          menuProfile.textContent = "Nostr Login";
        }
      }
      showSection('profile');
    });

    menuEvents.addEventListener('click', () => showSection('events'));

    menuAdmin.addEventListener('click', () => showSection('admin'));
  
    // Event Listener for Event Form Submission (for Admins)
    eventForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(eventForm);
      const eventData = {
        title: formData.get('event-title'),
        venue: formData.get('event-venue'),
        date: formData.get('event-date'),
        fee: formData.get('event-fee'),
        description: formData.get('event-description'),
        pubkey: localStorage.getItem('pubkey'),
      };
      console.log('Form data ready to be sent for event creation:', eventData);
      await createEvent(eventData);
      alert("Event created successfully!");
    });
  
    // Global variable to hold the authenticated user profile
    let userProfile = null;
  
    // Load public content (tracks) immediately
    fetchTracks();
  
    // --- Functions ---
  
    // Show a specific section and update active menu button
    function showSection(section) {
      librarySection.classList.remove('active');
      profileSection.classList.remove('active');
      adminSection.classList.remove('active');
      menuLibrary.classList.remove('active');
      menuProfile.classList.remove('active');
      menuEvents.classList.remove('active');
      menuAdmin.classList.remove('active');
  
      if (section === 'library') {
        librarySection.classList.add('active');
        menuLibrary.classList.add('active');
      } else if (section === 'profile') {
        profileSection.classList.add('active');
        menuProfile.classList.add('active');
      } else if (section === 'events') {
        eventsSection.classList.add('active');
        menuEvents.classList.add('active');
      } else if (section === 'admin') {
        adminSection.classList.add('active');
        menuAdmin.classList.add('active');
      }
    }
  
    // Fetch tracks (public content)
    function fetchTracks() {
      fetch("/tracks")
        .then(response => response.json())
        .then(data => {
          const songsSection = document.getElementById("songs-section");
          songsSection.innerHTML = "";
          if (data.tracks && data.tracks.length > 0) {
            data.tracks.forEach(track => {
              const trackElement = document.createElement("div");
              trackElement.classList.add("song-item");
              trackElement.innerHTML = `
                <h3>${track.title} by ${track.artist}</h3>
                <iframe src="https://embed.wavlake.com/track/${track.track_id}" width="100%" height="380" frameborder="0"></iframe>
              `;
              songsSection.appendChild(trackElement);
            });
          } else {
            songsSection.innerHTML = "<p>No songs available at this time.</p>";
          }
        })
        .catch(err => {
          console.error("Error fetching tracks:", err);
          document.getElementById("songs-section").innerHTML = "<p>Error loading songs.</p>";
        });
    }
  
    // Authenticate with Nostr (triggered only on button click)
    async function authenticateWithNostr() {
      if (!window.nostr) {
        console.error("NOSTR wallet not available.");
        return;
      }
      try {
        // Retrieve public key from the wallet
        const pubkey = await window.nostr.getPublicKey();
        console.log("Authenticated pubkey:", pubkey);
        localStorage.setItem('pubkey', pubkey);
  
        // Removed local dummy validation block
  
        // Fetch user profile from the backend
        const response = await fetch('/fetch-profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pubkey })
        });
        const validationResult = await response.json();
        if (validationResult.content) {
          userProfile = validationResult;
          console.log("Profile validated:", userProfile.content.name);
          displayProfile(userProfile);
          fetchFuzzedEvents(userProfile);
          // If the nip05 field contains your domain, reveal the admin menu
          const nip05 = userProfile.content.nip05 || "No NIP-05 found";
          console.log(`User NIP-05: ${nip05}`);
          if (nip05 && nip05.includes("fuzzedrecords.com")) {
            menuAdmin.classList.remove('admin-only');
            menuAdmin.style.display = "inline-block";
          }
        } else {
          console.error("Profile validation failed or content is missing:", validationResult);
        }
      } catch (error) {
        console.error("An error occurred during authentication:", error);
      }
    }
  
    // Fetch and display events (only for authenticated users)
    async function fetchFuzzedEvents(userProfile) {
      const eventsContainer = document.getElementById("events-section-content");
      if (!userProfile) {
        eventsContainer.innerHTML = "<p>Please log in to see events.</p>";
        return;
      }
      try {
        const response = await fetch("/fuzzed_events");
        const data = await response.json();
        console.log("Fetched events data:", data); // <-- Debug log
        eventsContainer.innerHTML = "";
        if (data.events && data.events.length > 0) {
          data.events.forEach(event => {
            const eventElement = document.createElement("div");
            eventElement.classList.add("event-item");
            eventElement.innerHTML = `
              <h3>${getTagValue(event.tags, 'title')}</h3>
              <p><strong>Venue:</strong> ${getTagValue(event.tags, 'venue')}</p>
              <p><strong>Date:</strong> ${new Date(getTagValue(event.tags, 'date')).toLocaleString()}</p>
              <p><strong>Fee:</strong> $${getTagValue(event.tags, 'fee')}</p>
              <p>${event.content}</p>
            `;
            eventElement.innerHTML += `
              <button class="generate-ticket-btn" data-event='${JSON.stringify(event)}'>Generate Ticket</button>
            `;
            eventsContainer.appendChild(eventElement);
          });
          // Attach event listener for the Generate Ticket buttons
          document.addEventListener('click', async function (e) {
            if (e.target && e.target.classList.contains('generate-ticket-btn')) {
              if (e.target.disabled) return;  // Prevent multiple clicks
              e.target.disabled = true;  
              const eventData = JSON.parse(e.target.getAttribute('data-event'));
              await generateTicketWithQRCode(eventData);
            }
          });          
        } else {
          eventsContainer.innerHTML = "<p>No events found from fuzzedrecords.com accounts.</p>";
        }
      } catch (error) {
        console.error("Error fetching events:", error);
        eventsContainer.innerHTML = "<p>Error loading events.</p>";
      }
    }    
  
    // Generate a ticket, display a QR code, and send a DM via Nostr
    async function generateTicketWithQRCode(eventData) {
      const ticket_id = crypto.randomUUID();
      const event_id = eventData.id;
      const event_name = getTagValue(eventData.tags, 'title');
      const ticketData = {
        ticket_id: ticket_id,
        event_id: event_id,
        pubkey: localStorage.getItem('pubkey'),
        event_name: event_name
      };
      const qrLink = `https://fuzzedrecords.com/generate_qr?ticket_id=${ticket_id}&event_id=${event_id}`;
      if (qrContainer) {
        qrContainer.innerHTML = '';
        new QRCode(qrContainer, { text: qrLink, width: 256, height: 256, correctLevel: QRCode.CorrectLevel.L });
        console.log("QR Link: ", qrLink);
        console.log("Ticket Data: ", ticketData);
        await sendTicketViaNostrDM(ticketData, qrLink);
      } else {
        console.error("QR Container not found.");
      }
    }
  
    // Helper to extract a tag's value from an event
    function getTagValue(tags, key) {
      const tag = tags.find(t => t[0] === key);
      return tag ? tag[1] : 'N/A';
    }
  
    // Create an event (for admin users) by signing and sending the event
    async function createEvent(eventData) {
      try {
        console.log('Initiating creation of event with data:', eventData);
        if (!window.nostr) {
          throw new Error("NOSTR wallet not available.");
        }
        const eventTemplate = {
          kind: 52,
          created_at: Math.floor(Date.now() / 1000),
          tags: [
            ["title", eventData.title],
            ["venue", eventData.venue],
            ["date", eventData.date],
            ["fee", String(eventData.fee)]
          ],
          content: eventData.description,
          pubkey: eventData.pubkey
        };
        console.log('Event template before signing:', eventTemplate);
        const signedEvent = await window.nostr.signEvent(eventTemplate);
        if (!signedEvent.sig) {
          console.error("Failed to sign event. Ensure your Nostr wallet is active.");
          alert("Could not sign event. Please check your Nostr wallet.");
          return;
        }
        if (signedEvent.pubkey !== localStorage.getItem('pubkey')) {
          console.error("Mismatch: Signed event pubkey does not match logged-in user.");
          alert("Your signed event does not match your authenticated profile. Try again.");
          return;
        }        
        console.log('Signed event:', signedEvent);
        const response = await fetch('/create_event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...eventTemplate,
            sig: signedEvent.sig
          }),
        });
        if (!response.ok) {
          const errorData = await response.json();
          console.error('Error creating event:', errorData);
          alert('Failed to create event: ' + (errorData.error || 'Unknown error'));
          return;
        }
        const result = await response.json();
        console.log('Event created successfully:', result);
        alert('Event created successfully!');
      } catch (error) {
        console.error('An error occurred while creating the event:', error);
        alert('An error occurred while creating the event.');
      }
    }
  
    // Display user profile in the profile section
    function displayProfile(profileData) {
      const profileContainer = document.getElementById('profile-container');
      profileContainer.innerHTML = '';
      if (profileData.content) {
        const content = profileData.content;
        if (content.picture) {
          const img = document.createElement('img');
          img.src = content.picture;
          img.alt = content.name || 'Profile Picture';
          img.classList.add('profile-pic');
          profileContainer.appendChild(img);
        }
        const detailsTable = document.createElement('table');
        detailsTable.classList.add('profile-details');
        const details = [
          { label: 'Username', value: content.name },
          { label: 'NIP-05', value: content.nip05 },
          { label: 'LUD-16', value: content.lud16 },
          { label: 'Website', value: content.website },
          { label: 'About', value: content.about }
        ];
        details.forEach(detail => {
          if (detail.value) {
            const row = document.createElement('tr');
            const labelCell = document.createElement('td');
            labelCell.textContent = detail.label;
            const valueCell = document.createElement('td');
            if (detail.label === 'NIP-05' && detail.value.includes('@')) {
              const link = document.createElement('a');
              const parts = detail.value.split('@');
              link.href = `https://${parts[1]}/.well-known/nostr.json?name=${parts[0]}`;
              link.textContent = detail.value;
              valueCell.appendChild(link);
            } else {
              valueCell.textContent = detail.value;
            }
            row.appendChild(labelCell);
            row.appendChild(valueCell);
            detailsTable.appendChild(row);
          }
        });
        profileContainer.appendChild(detailsTable);
      } else {
        profileContainer.innerHTML = "<p class='empty-profile'>No profile data available.</p>";
      }
    }
  
    // Send a ticket via Nostr DM (unchanged)
    async function sendTicketViaNostrDM(ticketData, qrLink) {
        if (!window.nostr) return console.error("NOSTR wallet not available.");
      
        const messageContent = `
          [EVENT_ID]: ${ticketData.event_id}
          [TICKET_ID]: ${ticketData.ticket_id}
          Event: ${ticketData.event_name}
          Your ticket QR code: ${qrLink}
        `;
      
        try {
          const encryptedMessage = (window.nostr.nip44 && typeof window.nostr.nip44.encrypt === 'function')
            ? await window.nostr.nip44.encrypt(ticketData.pubkey, messageContent)
            : messageContent;
      
          const dmEvent = {
            kind: 14,
            created_at: Math.floor(Date.now() / 1000),
            tags: [["p", ticketData.pubkey]],
            content: encryptedMessage,
            pubkey: localStorage.getItem('pubkey')
          };
      
          const signedDM = await window.nostr.signEvent(dmEvent);
          console.log("Signed Message: ", signedDM);
          await fetch('/send_ticket', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(signedDM)
          })
          .then(response => response.json())
          .then(result => {
            if (result.status === "sent") {
              // Notify user of success
              alert("Success! Check your Nostr DMs for your event ticket.");
            } else {
              // Notify user of failure
              alert("Failed to send ticket. Please try again.");
            }
          })
          .catch(error => {
            console.error("Error sending DM:", error);
            const regStatus = document.getElementById('registration-status');
            if (regStatus) {
              regStatus.innerText = "Registration failed. Please try again.";
            }
          });
        } catch (error) {
          console.error("Error in sendTicketViaNostrDM:", error);
        }
      }      
  });
  
