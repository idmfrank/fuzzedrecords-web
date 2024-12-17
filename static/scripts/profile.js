document.addEventListener('DOMContentLoaded', function () {
    authenticateWithNostr();
    // NOSTR Authentication
    async function authenticateWithNostr() {
        if (!window.nostr) {
            console.error("NOSTR wallet not available.");
            return;
        }

        try {
            const pubkey = await window.nostr.getPublicKey();
            console.log("Public Key (hex) returned by NOSTR wallet:", pubkey);

            // Fetch the profile data from the server
            const response = await fetch('/fetch-profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ pubkey: pubkey })
            });

            const profileData = await response.json();

            if (profileData.error) {
                console.error("Error fetching profile:", profileData.error);
                return;
            }

            console.log("Profile Data:", profileData);
            displayProfile(profileData);

        } catch (error) {
            console.error("An error occurred during authentication:", error);
        }
    }

    function displayProfile(profileData) {
        const profileContainer = document.getElementById('profile-container');
        const introSection = document.getElementById('intro-section');

        if (!profileContainer) {
            console.error("Profile container element not found.");
            return;
        }

        // Clear the container to ensure no stale content
        profileContainer.innerHTML = "";

        if (profileData.content) {
            // Hide the intro section when a profile is found
            if (introSection) {
                introSection.style.display = 'none';
            }

            const content = profileData.content;

            // Display profile picture
            if (content.picture) {
                const img = document.createElement('img');
                img.src = content.picture;
                img.alt = content.display_name || 'Profile Picture';
                img.classList.add('profile-pic');
                profileContainer.appendChild(img);
            }

            // Display profile name
            if (content.display_name) {
                const nameElement = document.createElement('h2');
                nameElement.textContent = content.display_name;
                profileContainer.appendChild(nameElement);
            }

            // Create and populate the details table
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
            // Show the intro section if no profile is found
            if (introSection) {
                introSection.style.display = 'block';
            }
        }
    }
});
