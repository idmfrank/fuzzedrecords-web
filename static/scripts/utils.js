// utils.js - shared helper functions
const PUBLIC_SECTIONS = ['listen', 'bands', 'submit', 'support', 'about'];

// Highlight the active public navigation link and optionally scroll to a section.
export function showSection(section) {
  const targetSection = PUBLIC_SECTIONS.includes(section) ? section : 'listen';
  PUBLIC_SECTIONS.forEach(sec => {
    const el = document.getElementById(sec);
    const btn = document.getElementById(`menu-${sec}`);
    if (el) el.classList.toggle('active', sec === targetSection);
    if (btn) btn.classList.toggle('active', sec === targetSection);
  });

  const el = document.getElementById(targetSection);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

export function getPublicSections() {
  return [...PUBLIC_SECTIONS];
}

// Extract single-letter tag value from event tags
export function getTagValue(tags, key) {
  if (!Array.isArray(tags)) return 'N/A';
  const tag = tags.find(t => t[0] === key);
  return tag && tag[1] ? tag[1] : 'N/A';
}
