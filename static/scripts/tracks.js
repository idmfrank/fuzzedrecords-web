// tracks.js
// Handles fetching and rendering the Wavlake direct-support library.

function firstPresent(...values) {
  return values.find(value => typeof value === 'string' && value.trim())?.trim() || null;
}

function trackSupportUrl(track) {
  return firstPresent(
    track.wavlake_url,
    track.wavlakeUrl,
    track.wavlake_track_url,
    track.wavlakeTrackUrl,
    track.url,
    track.link,

  ) || (track.track_id ? `https://wavlake.com/track/${encodeURIComponent(track.track_id)}` : null);
}

function trackTitle(track) {
  return firstPresent(track.title, track.name, track.track_title, track.trackTitle) || 'Untitled Wavlake track';
}

function artistName(track) {
  return firstPresent(track.artist, track.artist_name, track.artistName, track.creator, track.author) || 'Artist not listed';
}

function albumName(track) {
  return firstPresent(track.album, track.album_title, track.albumTitle, track.release, track.collection) || 'Album not listed';
}

function artworkUrl(track) {
  return firstPresent(track.artwork, track.artwork_url, track.artworkUrl, track.album_art, track.albumArt, track.image, track.image_url);
}

function renderTrack(track) {
  const trackElement = document.createElement('article');
  trackElement.classList.add('song-item');

  const artwork = artworkUrl(track);
  if (artwork) {
    const image = document.createElement('img');
    image.classList.add('track-artwork');
    image.src = artwork;
    image.alt = `${trackTitle(track)} artwork`;
    image.loading = 'lazy';
    trackElement.appendChild(image);
  }

  const heading = document.createElement('h3');
  heading.textContent = trackTitle(track);
  trackElement.appendChild(heading);

  const meta = document.createElement('p');
  meta.classList.add('track-meta');
  meta.textContent = `${artistName(track)} · ${albumName(track)}`;
  trackElement.appendChild(meta);

  if (track.track_id) {
    const iframe = document.createElement('iframe');
    iframe.title = `${trackTitle(track)} on Wavlake`;
    iframe.src = `https://embed.wavlake.com/track/${encodeURIComponent(track.track_id)}`;
    iframe.width = '100%';
    iframe.height = '380';
    iframe.frameBorder = '0';
    iframe.loading = 'lazy';
    trackElement.appendChild(iframe);
  } else {
    const playerFallback = document.createElement('p');
    playerFallback.classList.add('fallback-copy');
    playerFallback.textContent = 'Embedded Wavlake player is not available for this track yet.';
    trackElement.appendChild(playerFallback);
  }

  const supportUrl = trackSupportUrl(track);
  if (supportUrl) {
    const links = document.createElement('div');
    links.classList.add('track-links');

    const wavlakeLink = document.createElement('a');
    wavlakeLink.href = supportUrl;
    wavlakeLink.target = '_blank';
    wavlakeLink.rel = 'noopener noreferrer';
    wavlakeLink.textContent = 'Boost on Wavlake';
    links.appendChild(wavlakeLink);
    trackElement.appendChild(links);
  }

  return trackElement;
}

export async function fetchTracks() {
  const songsSection = document.getElementById('songs-section');
  if (!songsSection) return;

  songsSection.innerHTML = '<p class="fallback-copy">Loading archive and support links…</p>';

  try {
    const response = await fetch('/tracks');
    if (!response.ok) throw new Error(`Tracks request failed: ${response.status}`);

    const data = await response.json();
    const tracks = Array.isArray(data.tracks) ? data.tracks : [];
    songsSection.innerHTML = '';

    if (tracks.length > 0) {
      tracks.forEach(track => songsSection.appendChild(renderTrack(track || {})));
    } else {
      songsSection.innerHTML = '<p class="fallback-copy">No Wavlake archive tracks are available right now. You can still listen on SoundCloud above.</p>';
    }
  } catch (err) {
    console.error('Error fetching tracks:', err);
    songsSection.innerHTML = '<p class="fallback-copy">Wavlake archive/support links could not load right now. The SoundCloud player above is still available.</p>';
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', fetchTracks);
