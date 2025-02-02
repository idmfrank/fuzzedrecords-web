document.addEventListener('DOMContentLoaded', function () {
    const menuLibrary = document.getElementById('menu-library');
    const menuProfile = document.getElementById('menu-profile');
    const menuAdmin = document.getElementById('menu-admin');
    const librarySection = document.getElementById('library-section');
    const profileSection = document.getElementById('profile-section');
    const adminSection = document.getElementById('admin-section');
    const eventForm = document.getElementById('event-form');

    // Default: Show library section
    showSection('library');

    // Event Listeners for Menu
    menuLibrary.addEventListener('click', () => showSection('library'));
    menuProfile.addEventListener('click', () => showSection('profile'));
    menuAdmin.addEventListener('click', () => showSection('admin'));

    // Event Listener for Event Form Submission
    eventForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(eventForm);
        const eventData = {
            title: formData.get('event-title'),
            venue: formData.get('event-venue'),
            date: formData.get('event-date'),
            price: formData.get('event-price'),
            description: formData.get('event-description'),
            pubkey: localStorage.getItem('pubkey'), // Add pubkey to event data
        };

        console.log('Form data ready to be sent for event creation:', eventData);
        await createEvent(eventData);
        alert("Event created successfully!");
    });

    // Authentication with NOSTR
    authenticateWithNostr();

    async function authenticateWithNostr() {
        if (!window.nostr) {
            console.error("NOSTR wallet not available.");
            return;
        }

        try {
            const pubkey = await window.nostr.getPublicKey(); // Retrieve pubkey
            console.log("Authenticated pubkey:", pubkey); // Log for debugging
            localStorage.setItem('pubkey', pubkey); // Save pubkey for later use
            const response = await fetch('/fetch-profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pubkey: pubkey })
            });

            const validationResult = await response.json();
            if (validationResult.content) {
                console.log("Validation Result prior to Validation for username: ", validationResult.content.name);
                displayProfile(validationResult);
                if (validationResult.content.nip05 && validationResult.content.nip05.includes("fuzzedrecords.com")) {
                    menuAdmin.classList.remove('admin-only');
                }
            } else {
                console.error("Profile validation failed or content is missing:", validationResult);
            }
        } catch (error) {
            console.error("An error occurred during authentication:", error);
        }
    }

    async function createEvent(eventData) {
        try {
            console.log('Initiating creation of event with data:', eventData);
            if (!window.nostr) {
                throw new Error("NOSTR wallet not available.");
            }
    
            const eventTemplate = {
                kind: 52, // Must match server-side kind
                created_at: Math.floor(Date.now() / 1000),
                tags: [
                    ["title", eventData.title],
                    ["venue", eventData.venue],
                    ["date", eventData.date],
                    ["price", String(eventData.price)]
                ],
                content: eventData.description,
                pubkey: eventData.pubkey
            };
    
            console.log('Event template before signing:', eventTemplate);
    
            // Request the NOSTR wallet to sign the event template
            const signedEvent = await window.nostr.signEvent(eventTemplate);
            console.log('Signed event:', signedEvent);
    
            // Send the signed event to the server
            const response = await fetch('/create_event', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...eventTemplate,
                    sig: signedEvent.sig  // Include the signature
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

    function displayProfile(profileData) {
        const profileContainer = document.getElementById('profile-container');
        profileContainer.innerHTML = ''; // Clear existing content

        if (profileData.content) {
            const content = profileData.content;

            // Profile Picture
            if (content.picture) {
                const img = document.createElement('img');
                img.src = content.picture;
                img.alt = content.display_name || 'Profile Picture';
                img.classList.add('profile-pic');
                profileContainer.appendChild(img);
            }

            // Details Table
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
                        link.href = `https://${detail.value.split('@')[1]}/.well-known/nostr.json?name=${detail.value.split('@')[0]}`;
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

    // Fetch and Display Songs
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

    // Helper: Show Section
    function showSection(section) {
        librarySection.classList.remove('active');
        profileSection.classList.remove('active');
        adminSection.classList.remove('active');
        menuLibrary.classList.remove('active');
        menuProfile.classList.remove('active');
        menuAdmin.classList.remove('active');

        if (section === 'library') {
            librarySection.classList.add('active');
            menuLibrary.classList.add('active');
        } else if (section === 'profile') {
            profileSection.classList.add('active');
            menuProfile.classList.add('active');
        } else if (section === 'admin') {
            adminSection.classList.add('active');
            menuAdmin.classList.add('active');
        }
    }
});