// tracks.js
// Handles fetching and rendering the music library
export async function fetchTracks() {
  const songsSection = document.getElementById('songs-section');
  try {
    const response = await fetch('/tracks');
    const data = await response.json();
    songsSection.innerHTML = '';
    if (data.tracks && data.tracks.length > 0) {
      data.tracks.forEach(track => {
        const trackElement = document.createElement('div');
        trackElement.classList.add('song-item');

        const heading = document.createElement('h3');
        heading.textContent = `${track.title} by ${track.artist}`;

        const iframe = document.createElement('iframe');
        iframe.src = `https://embed.wavlake.com/track/${encodeURIComponent(track.track_id)}`;
        iframe.width = '100%';
        iframe.height = '380';
        iframe.frameBorder = '0';

        trackElement.appendChild(heading);
        trackElement.appendChild(iframe);
        songsSection.appendChild(trackElement);
      });
    } else {
      songsSection.innerHTML = '<p>No songs available at this time.</p>';
    }
  } catch (err) {
    console.error('Error fetching tracks:', err);
    songsSection.innerHTML = '<p>Error loading songs.</p>';
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', fetchTracks);
