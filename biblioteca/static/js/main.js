document.addEventListener('DOMContentLoaded', function(){
  document.body.classList.add('page-fade');

  document.querySelectorAll('.doc-card').forEach((el, i) => {
    el.style.animationDelay = (i * 60) + 'ms';
  });

  // Autocompletado para biblioteca virtual (datalist)
  const datalist = document.getElementById('titulos-list');
  const inputSearch = document.getElementById('doc-search');
  if (datalist && inputSearch) {
    fetch('/api/documentos/titulos')
      .then(res => res.ok ? res.json() : Promise.reject(res.status))
      .then(titulos => {
        datalist.innerHTML = titulos.map(t => `<option value="${escapeHtml(t)}">`).join('');
      })
      .catch(() => {
        // silencioso si falla (no rompe la página)
      });

    // helper para evitar inyección en opciones
    function escapeHtml(str) {
      return String(str).replace(/[&<>"']/g, (s) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
    }
  }
});

function uploadWithProgress(formElement, progressBarElement, onComplete){
  const formData = new FormData(formElement);
  const xhr = new XMLHttpRequest();
  xhr.open('POST', formElement.action);
  xhr.upload.addEventListener('progress', e => {
    if(e.lengthComputable){
      const pct = Math.round((e.loaded / e.total) * 100);
      progressBarElement.style.width = pct + '%';
    }
  });
  xhr.addEventListener('load', () => onComplete(xhr));
  xhr.send(formData);
}