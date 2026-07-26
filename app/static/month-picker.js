// Progressively enhances every input[name="budget_month"] (type="month") into
// a compact calendar-style month/year picker, consistent across browsers (native
// month inputs render very inconsistently — no picker at all in desktop Firefox).
// Also keeps it in sync with its paired "date" field until the user picks a
// month manually, so the common case (no override) needs no extra input.
document.addEventListener('DOMContentLoaded', function () {
  var MONTH_NAMES = window.MONTH_NAMES || [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  function formatDisplay(value) {
    if (!value) return '';
    var year = parseInt(value.slice(0, 4), 10);
    var month = parseInt(value.slice(5, 7), 10);
    if (!year || !month) return value;
    return MONTH_NAMES[month - 1] + ' ' + year;
  }

  var openState = null; // { popup, displayInput }

  function closePopup() {
    if (!openState) return;
    openState.popup.remove();
    window.removeEventListener('scroll', closePopup, true);
    window.removeEventListener('resize', closePopup);
    openState = null;
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('.month-picker-popup') || e.target.classList.contains('month-picker-display')) return;
    closePopup();
  });

  function openPicker(displayInput, currentValue, onPick) {
    if (openState && openState.displayInput === displayInput) {
      closePopup();
      return;
    }
    closePopup();

    var today = new Date();
    var year = currentValue ? parseInt(currentValue.slice(0, 4), 10) : today.getFullYear();

    var popup = document.createElement('div');
    popup.className = 'month-picker-popup';
    document.body.appendChild(popup);

    function render() {
      popup.innerHTML = '';

      var header = document.createElement('div');
      header.className = 'month-picker-header';
      var prev = document.createElement('button');
      prev.type = 'button';
      prev.className = 'month-picker-nav';
      prev.textContent = '‹';
      prev.addEventListener('click', function (e) {
        e.stopPropagation();
        year -= 1;
        render();
      });
      var label = document.createElement('span');
      label.textContent = year;
      var next = document.createElement('button');
      next.type = 'button';
      next.className = 'month-picker-nav';
      next.textContent = '›';
      next.addEventListener('click', function (e) {
        e.stopPropagation();
        year += 1;
        render();
      });
      header.append(prev, label, next);
      popup.appendChild(header);

      var grid = document.createElement('div');
      grid.className = 'month-picker-grid';
      MONTH_NAMES.forEach(function (name, idx) {
        var m = idx + 1;
        var cellValue = year + '-' + String(m).padStart(2, '0');
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'month-picker-cell';
        btn.textContent = name.slice(0, 4);
        btn.title = name;
        if (currentValue === cellValue) btn.classList.add('month-picker-selected');
        if (today.getFullYear() === year && today.getMonth() + 1 === m) {
          btn.classList.add('month-picker-today');
        }
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          currentValue = cellValue;
          onPick(cellValue);
          closePopup();
        });
        grid.appendChild(btn);
      });
      popup.appendChild(grid);
    }
    render();

    var rect = displayInput.getBoundingClientRect();
    popup.style.top = (rect.bottom + 4) + 'px';
    var left = rect.left;
    var maxLeft = window.innerWidth - popup.offsetWidth - 8;
    if (left > maxLeft) left = Math.max(8, maxLeft);
    popup.style.left = left + 'px';

    openState = { popup: popup, displayInput: displayInput };
    window.addEventListener('scroll', closePopup, true);
    window.addEventListener('resize', closePopup);
  }

  document.querySelectorAll('input[name="budget_month"]').forEach(function (original) {
    var display = document.createElement('input');
    display.type = 'text';
    display.readOnly = true;
    display.className = (original.className + ' month-picker-display').trim();
    display.style.cssText = original.style.cssText;
    display.value = formatDisplay(original.value);

    original.type = 'hidden';
    original.parentNode.insertBefore(display, original);

    var monthTouched = false;

    display.addEventListener('click', function (e) {
      e.stopPropagation();
      openPicker(display, original.value, function (newValue) {
        monthTouched = true;
        original.value = newValue;
        display.value = formatDisplay(newValue);
      });
    });

    var formId = original.getAttribute('form');
    var dateInput = formId
      ? document.querySelector('input[name="date"][form="' + formId + '"]')
      : (original.closest('form') ? original.closest('form').querySelector('input[name="date"]') : null);

    if (dateInput) {
      dateInput.addEventListener('input', function () {
        if (monthTouched || !this.value) return;
        var newValue = this.value.slice(0, 7);
        original.value = newValue;
        display.value = formatDisplay(newValue);
      });
    }
  });
});
