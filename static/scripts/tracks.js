// tracks.js
// Handles fetching and rendering the music library
const SOUNDCLOUD_URL = 'https://soundcloud.com/fuzzedrecords';

function trackSupportUrl(track) {
  return track.url || track.link || track.wavlake_url || track.wavlakeUrl || (track.track_id ? `https://wavlake.com/track/${encodeURIComponent(track.track_id)}` : null);
}

export async function fetchTracks() {
  const songsSection = document.getElementById('songs-section');
  if (!songsSection) return;

  try {
    const response = await fetch('/tracks');
    if (!response.ok) throw new Error(`Tracks request failed: ${response.status}`);

    const data = await response.json();
    songsSection.innerHTML = '';
    if (data.tracks && data.tracks.length > 0) {
      data.tracks.forEach(track => {
        const trackElement = document.createElement('article');
        trackElement.classList.add('song-item');

        const heading = document.createElement('h3');
        heading.textContent = track.title || 'Untitled track';

        const artist = document.createElement('p');
        artist.classList.add('track-artist');
        artist.textContent = track.artist ? `Artist: ${track.artist}` : 'Artist: Fuzzed Records';

        trackElement.appendChild(heading);
        trackElement.appendChild(artist);

        if (track.track_id) {
          const iframe = document.createElement('iframe');
          iframe.title = `${track.title || 'Track'} on Wavlake`;
          iframe.src = `https://embed.wavlake.com/track/${encodeURIComponent(track.track_id)}`;
          iframe.width = '100%';
          iframe.height = '380';
          iframe.frameBorder = '0';
          iframe.loading = 'lazy';
          trackElement.appendChild(iframe);
        }

        const links = document.createElement('div');
        links.classList.add('track-links');

        const soundcloudLink = document.createElement('a');
        soundcloudLink.href = SOUNDCLOUD_URL;
        soundcloudLink.target = '_blank';
        soundcloudLink.rel = 'noopener noreferrer';
        soundcloudLink.textContent = 'Listen on SoundCloud';
        links.appendChild(soundcloudLink);

        const supportUrl = trackSupportUrl(track);
        if (supportUrl) {
          const wavlakeLink = document.createElement('a');
          wavlakeLink.href = supportUrl;
          wavlakeLink.target = '_blank';
          wavlakeLink.rel = 'noopener noreferrer';
          wavlakeLink.textContent = 'Support on Wavlake';
          links.appendChild(wavlakeLink);
        }

        trackElement.appendChild(links);
        songsSection.appendChild(trackElement);
      });
    } else {
      songsSection.innerHTML = '<p class="fallback-copy">No Wavlake direct-support tracks are available right now. You can still listen and follow Fuzzed Records on <a href="https://soundcloud.com/fuzzedrecords" target="_blank" rel="noopener noreferrer">SoundCloud</a>.</p>';
    }
  } catch (err) {
    console.error('Error fetching tracks:', err);
    songsSection.innerHTML = '<p class="fallback-copy">Wavlake tracks could not be loaded right now. Please listen on <a href="https://soundcloud.com/fuzzedrecords" target="_blank" rel="noopener noreferrer">SoundCloud</a> and check back later for direct-support links.</p>';
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', fetchTracks);
