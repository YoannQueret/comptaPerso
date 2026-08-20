// Rebuilds a category <select>'s options to match whichever account is picked in
// an account <select>, using a {owner_id: [{id, full_name}, ...]} map embedded in
// the page. Needed because a shared account's transactions/rules always use the
// ACCOUNT OWNER's categories, and a single form can now offer accounts owned by
// more than one person (the user's own + whatever's shared with them).
function syncCategoryOptions(accountSelectId, categorySelectId, categoriesByOwner) {
  var accSel = document.getElementById(accountSelectId);
  var catSel = document.getElementById(categorySelectId);
  if (!accSel || !catSel) return;

  function rebuild() {
    var option = accSel.options[accSel.selectedIndex];
    var ownerId = option ? option.getAttribute('data-owner') : null;
    var cats = (ownerId && categoriesByOwner[ownerId]) || [];
    var keepId = catSel.value;

    catSel.textContent = '';
    var blank = document.createElement('option');
    blank.value = '';
    blank.textContent = '—';
    catSel.appendChild(blank);

    for (var i = 0; i < cats.length; i++) {
      var opt = document.createElement('option');
      opt.value = cats[i].id;
      opt.textContent = cats[i].full_name;
      if (cats[i].id === keepId) opt.selected = true;
      catSel.appendChild(opt);
    }
  }

  accSel.addEventListener('change', rebuild);
  rebuild();
}
