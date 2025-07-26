// utils.js - shared helper functions
// Switch between content sections
export function showSection(section) {
  const sections = ['library', 'profile', 'events', 'admin', 'gear'];
  sections.forEach(sec => {
    const el = document.getElementById(`${sec}-section`);
    const btn = document.getElementById(`menu-${sec}`);
    if (el) el.classList.toggle('active', sec === section);
    if (btn) btn.classList.toggle('active', sec === section);
  });
  const logo = document.getElementById('header-logo');
  if (logo) {
    if (section === 'gear') {
      logo.src = '/static/images/fuzzed-guitars-logo.jfif';
    } else {
      logo.src = '/static/images/fuzzedrecords.png';
    }
  }
}

// Extract single-letter tag value from event tags
export function getTagValue(tags, key) {
  if (!Array.isArray(tags)) return 'N/A';
  const tag = tags.find(t => t[0] === key);
  return tag && tag[1] ? tag[1] : 'N/A';
}