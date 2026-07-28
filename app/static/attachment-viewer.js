// Shared <dialog> popup that previews a transaction's attachment inline
// (image or PDF) instead of opening it in a new tab.
function openAttachment(url, ext, openInNewTabLabel) {
  var dialog = document.getElementById('attachment-dialog');
  var content = document.getElementById('attachment-dialog-content');
  content.innerHTML = '';

  if ((ext || '').toLowerCase() === 'pdf') {
    var iframe = document.createElement('iframe');
    iframe.src = url;
    iframe.className = 'attachment-frame';
    content.appendChild(iframe);

    var fallback = document.createElement('p');
    fallback.className = 'muted';
    var link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = openInNewTabLabel;
    fallback.appendChild(link);
    content.appendChild(fallback);
  } else {
    var img = document.createElement('img');
    img.src = url;
    img.className = 'attachment-image';
    content.appendChild(img);
  }

  dialog.showModal();
}
