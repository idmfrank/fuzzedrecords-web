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
        trackElement.innerHTML = `
          <h3>${track.title} by ${track.artist}</h3>
          <iframe src="https://embed.wavlake.com/track/${track.track_id}" width="100%" height="380" frameborder="0"></iframe>
        `;
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