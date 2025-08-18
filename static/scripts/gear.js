document.addEventListener('DOMContentLoaded', () => {
  const buttons = document.querySelectorAll('.gear-submenu button');
  const items = document.querySelectorAll('#gear-items .gear-item');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      items.forEach(item => {
        item.classList.toggle('active', item.id === target);
      });
      buttons.forEach(b => b.classList.toggle('active', b === btn));
    });
  });
});
