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

  document.querySelectorAll('.gear-gallery').forEach(gallery => {
    const images = gallery.querySelectorAll('img');
    const prev = gallery.querySelector('.prev');
    const next = gallery.querySelector('.next');
    const caption = gallery.parentElement.querySelector('.gear-caption');
    let index = 0;

    const showImage = i => {
      images.forEach((img, idx) => img.classList.toggle('active', idx === i));
      if (caption) {
        caption.textContent = images[i].alt;
      }
    };

    prev.addEventListener('click', () => {
      index = (index - 1 + images.length) % images.length;
      showImage(index);
    });

    next.addEventListener('click', () => {
      index = (index + 1) % images.length;
      showImage(index);
    });

    showImage(index);
  });
});
