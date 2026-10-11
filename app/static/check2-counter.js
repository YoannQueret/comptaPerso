// Shows a discreet running total of the amounts whose row is ticked in the
// second, non-persisted checkbox column (transactions / monthly budget
// tables) — purely client-side, since that column itself resets on every
// reload. Positioned to start right above that column's own "S" header.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-check2-counter]').forEach(function (counterEl) {
    var table = document.getElementById(counterEl.getAttribute('data-check2-counter'));
    if (!table) return;
    var template = counterEl.getAttribute('data-template') || '{total}';

    function updateTotal() {
      var total = 0;
      var currency = '';
      var any = false;
      table.querySelectorAll('.check2:checked').forEach(function (cb) {
        var amount = parseFloat(cb.getAttribute('data-amount'));
        if (!isNaN(amount)) {
          total += amount;
          any = true;
          currency = currency || cb.getAttribute('data-currency') || '';
        }
      });
      counterEl.textContent = any
        ? template.replace('{total}', total.toFixed(2) + (currency ? ' ' + currency : ''))
        : '';
    }

    function updatePosition() {
      var checkHeaders = table.querySelectorAll('thead th.col-check');
      var sHeader = checkHeaders[checkHeaders.length - 1];
      var wrap = counterEl.parentElement;
      if (!sHeader || !wrap) return;
      var wrapRect = wrap.getBoundingClientRect();
      var thRect = sHeader.getBoundingClientRect();
      counterEl.style.left = (thRect.left - wrapRect.left) + 'px';
    }

    table.addEventListener('change', function (e) {
      if (e.target.classList.contains('check2')) updateTotal();
    });
    window.addEventListener('resize', updatePosition);
    updateTotal();
    updatePosition();
  });
});
