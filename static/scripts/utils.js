// utils.js - shared helper functions
const PUBLIC_SECTIONS = ['listen', 'support', 'future-bands', 'about'];

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

document.addEventListener('DOMContentLoaded', () => {
  const setActiveFromHash = () => {
    const section = window.location.hash.slice(1);
    highlightSection(PUBLIC_SECTIONS.includes(section) ? section : 'listen');
  };

  setActiveFromHash();
  window.addEventListener('hashchange', setActiveFromHash);
});
