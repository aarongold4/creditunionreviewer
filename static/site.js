// Credit Union Reviewer — nav toggle + table sort
(function () {
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.querySelector('.site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  document.querySelectorAll('table.data-table th[data-sort]').forEach(function (th) {
    th.addEventListener('click', function () {
      var table = th.closest('table');
      var tbody = table.querySelector('tbody');
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      var asc = th.dataset.dir !== 'asc';
      table.querySelectorAll('th').forEach(function (h) { delete h.dataset.dir; });
      th.dataset.dir = asc ? 'asc' : 'desc';
      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
      rows.sort(function (a, b) {
        var av = a.children[idx].textContent.trim().toLowerCase();
        var bv = b.children[idx].textContent.trim().toLowerCase();
        var an = parseFloat(av.replace(/[^0-9.\-]/g, ''));
        var bn = parseFloat(bv.replace(/[^0-9.\-]/g, ''));
        if (!isNaN(an) && !isNaN(bn) && av.match(/\d/) && bv.match(/\d/)) {
          return asc ? an - bn : bn - an;
        }
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });
})();
