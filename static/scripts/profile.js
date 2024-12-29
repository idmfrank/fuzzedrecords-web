document.addEventListener('DOMContentLoaded', function () {
    authenticateWithNostr();

    async function authenticateWithNostr() {
        if (!window.nostr) {
            console.error("NOSTR wallet not available.");
            return;
        }

        try {
            const pubkey = await window.nostr.getPublicKey();
            console.log("Public Key (hex) returned by NOSTR wallet:", pubkey);

            // Fetch and validate the profile
            const response = await fetch('/validate-profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ pubkey: pubkey })
            });

            const validationResult = await response.json();

            if (response.ok) {
                console.log("Profile is valid and verified:", validationResult);
                displayProfile(validationResult); // Use the validated data to display
            } else {
                console.error("Profile validation failed:", validationResult.error);
                alert("Your profile could not be validated. Please ensure you are NIP-05 verified.");
            }
        } catch (error) {
            console.error("An error occurred during authentication:", error);
        }
    }

    async function createEvent(eventData) {
        if (!window.nostr) {
            console.error("NOSTR wallet not available.");
            return;
        }
    
        try {
            const pubkey = await window.nostr.getPublicKey();
    
            // Construct event to be signed
            const unsignedEvent = {
                kind: 52,
                pubkey: pubkey,
                created_at: Math.floor(Date.now() / 1000),
                tags: [
                    ["title", eventData.title],
                    ["venue", eventData.venue],
                    ["date", eventData.date],
                    ["price", eventData.price]
                ],
                content: eventData.description
            };
    
            // Sign the event with the user's wallet
            const signature = await window.nostr.signEvent(unsignedEvent);
    
            // Include signature and pubkey in the payload
            const payload = {
                ...eventData,
                pubkey: pubkey,
                sig: signature
            };
    
            // Send the signed event to the server
            const response = await fetch('/create_event', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
    
            const result = await response.json();
            if (response.ok) {
                console.log("Event created successfully:", result);
            } else {
                console.error("Error creating event:", result.error);
            }
        } catch (error) {
            console.error("An error occurred during event creation:", error);
        }
    }

    function displayProfile(profileData) {
        const profileContainer = document.getElementById('profile-container');
        const introSection = document.getElementById('intro-section');

        if (!profileContainer) {
            console.error("Profile container element not found.");
            return;
        }

        profileContainer.innerHTML = "";

        if (profileData.content) {
            if (introSection) {
                introSection.style.display = 'none';
            }

            const content = profileData.content;

            if (content.picture) {
                const img = document.createElement('img');
                img.src = content.picture;
                img.alt = content.display_name || 'Profile Picture';
                img.classList.add('profile-pic');
                profileContainer.appendChild(img);
            }

            if (content.display_name) {
                const nameElement = document.createElement('h2');
                nameElement.textContent = content.display_name;
                profileContainer.appendChild(nameElement);
            }

            const table = document.createElement('table');
            table.classList.add('profile-table');

            const details = [
                { label: 'Username', value: content.name },
                { label: 'NIP-05', value: content.nip05, isNip05: true },
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
                    if (detail.isNip05) {
                        const link = document.createElement('a');
                        link.href = `https://${detail.value.split('@')[1]}/.well-known/nostr.json?name=${detail.value.split('@')[0]}`;
                        link.textContent = detail.value;
                        valueCell.appendChild(link);
                    } else {
                        valueCell.textContent = detail.value;
                    }

                    row.appendChild(labelCell);
                    row.appendChild(valueCell);
                    table.appendChild(row);
                }
            });

            profileContainer.appendChild(table);
        } else {
            if (introSection) {
                introSection.style.display = 'block';
            }
        }
    }
});
