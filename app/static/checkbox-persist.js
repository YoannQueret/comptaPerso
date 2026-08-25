// Persists the "reviewed" tick mark (monthly budget / transactions pages) to
// the server as soon as it's toggled, so it's kept across reloads and visible
// to anyone else who can see the same transaction (e.g. a shared account's
// collaborators) — it has no effect on any balance/report, it's just a shared
// checklist aid.
document.addEventListener('DOMContentLoaded', function () {
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : null;

  document.querySelectorAll('input[type="checkbox"][data-toggle-url]').forEach(function (checkbox) {
    checkbox.addEventListener('change', function () {
      var wasChecked = !checkbox.checked;
      checkbox.disabled = true;
      fetch(checkbox.getAttribute('data-toggle-url'), {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
      })
        .then(function (resp) {
          if (!resp.ok) throw new Error('request failed');
        })
        .catch(function () {
          checkbox.checked = wasChecked; // revert on failure
        })
        .finally(function () {
          checkbox.disabled = false;
        });
    });
  });
});
