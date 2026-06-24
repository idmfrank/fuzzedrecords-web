// utils.js - shared helper functions
const PUBLIC_SECTIONS = ['listen', 'archive', 'support', 'future-bands', 'about'];

// Highlight the active public navigation link without hiding content or replacing anchor behavior.
export function highlightSection(section) {
  const targetSection = PUBLIC_SECTIONS.includes(section) ? section : 'listen';
  PUBLIC_SECTIONS.forEach(sec => {
    const btn = document.getElementById(`menu-${sec}`);
    if (btn) btn.classList.toggle('active', sec === targetSection);
  });
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
