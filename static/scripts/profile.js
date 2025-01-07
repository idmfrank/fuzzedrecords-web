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
            description: formData.get('event-description')
        };

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
            const pubkey = await window.nostr.getPublicKey();
            const response = await fetch('/validate-profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pubkey: pubkey })
            });

            console.info("Validate Profile returned the following response:", response.json.toString);

            const validationResult = await response.json();
            if (response.ok && validationResult.content) {
                displayProfile(validationResult);
                console.log("Validation Result: ", validationResult);
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

    function displayProfile(profileData) {
        const profileContainer = document.getElementById('profile-container');
        if (!profileContainer) {
            console.error("Profile container not found.");
            return;
        }
    
        profileContainer.innerHTML = ""; // Clear existing content
    
        if (profileData.content) {
            const content = profileData.content;
    
            // Add profile picture
            if (content.picture) {
                const img = document.createElement('img');
                img.src = content.picture;
                img.alt = content.display_name || 'Profile Picture';
                img.classList.add('profile-pic');
                profileContainer.appendChild(img);
            }
    
            // Add display name
            if (content.display_name) {
                const nameElement = document.createElement('h2');
                nameElement.textContent = content.display_name;
                profileContainer.appendChild(nameElement);
            }
    
            // Add additional profile details
            const detailsTable = document.createElement('table');
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
            profileContainer.innerHTML = "<p>No profile data available.</p>";
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
