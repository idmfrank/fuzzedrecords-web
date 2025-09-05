// shop.js - handle shop navigation and Lightning payments

function showShopButton() {
  const menuShop = document.getElementById('menu-shop');
  if (menuShop) {
    menuShop.style.display = 'inline-block';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const menuProfile = document.getElementById('menu-profile');
  const menuShop = document.getElementById('menu-shop');

  // Navigate to shop when clicking the button on index page
  if (menuShop) {
    menuShop.addEventListener('click', () => {
      window.location.href = '/shop';
    });
  }

  // Show shop button if already logged in
  if (sessionStorage.getItem('pubkey')) {
    showShopButton();
  }

  // Observe login state to reveal shop button after login
  if (menuProfile) {
    const observer = new MutationObserver(() => {
      if (menuProfile.dataset.loggedIn === 'true') {
        showShopButton();
        observer.disconnect();
      }
    });
    observer.observe(menuProfile, { attributes: true, attributeFilter: ['data-logged-in'] });
  }

  // Shop page payment handling and access control
  const lightningAddrElem = document.getElementById('lightning-address');
  if (lightningAddrElem) {
    // Redirect to home if not logged in
    if (!sessionStorage.getItem('pubkey')) {
      window.location.href = '/';
      return;
    }

    const addr = lightningAddrElem.textContent;
    const copyBtn = document.getElementById('copy-lightning');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(addr);
        copyBtn.textContent = 'Copied!';
        setTimeout(() => (copyBtn.textContent = 'Copy'), 2000);
      });
    }

    const qrEl = document.getElementById('lightning-qr');
    if (qrEl && window.QRCode) {
      new QRCode(qrEl, addr);
    }
  }
});
