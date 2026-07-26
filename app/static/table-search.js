// Instant, client-side table search (like DataTables' search box), with no
// extra request: filters rows already rendered in the page by matching their
// visible text, accent- and case-insensitive.
document.addEventListener('DOMContentLoaded', function () {
  function normalize(s) {
    return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  document.querySelectorAll('.table-search').forEach(function (input) {
    var table = document.getElementById(input.getAttribute('data-table'));
    if (!table || !table.tBodies.length) return;
    var tbody = table.tBodies[0];
    var rows = Array.prototype.slice.call(tbody.rows);

    var emptyRow = document.createElement('tr');
    emptyRow.className = 'table-search-empty';
    emptyRow.style.display = 'none';
    var emptyCell = document.createElement('td');
    emptyCell.colSpan = 100;
    emptyCell.className = 'muted';
    emptyCell.textContent = input.getAttribute('data-empty-label') || '';
    emptyRow.appendChild(emptyCell);
    tbody.appendChild(emptyRow);

    input.addEventListener('input', function () {
      var query = normalize(input.value.trim());
      var visibleCount = 0;
      rows.forEach(function (row) {
        var match = !query || normalize(row.textContent).indexOf(query) !== -1;
        row.style.display = match ? '' : 'none';
        if (match) visibleCount += 1;
      });
      emptyRow.style.display = (query && visibleCount === 0) ? '' : 'none';
    });
  });
});
