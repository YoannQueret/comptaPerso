// Shrinks a photo attachment client-side before upload — phone cameras now
// routinely produce multi-megabyte images, most of which is far more detail
// than a receipt/invoice needs. PDFs and already-small files are left alone;
// if decoding fails (e.g. a HEIC photo this browser can't render), the
// original file is uploaded unchanged rather than blocking the user.
(function () {
  var MAX_DIMENSION = 1920;
  var JPEG_QUALITY = 0.8;
  var SKIP_BELOW_BYTES = 1024 * 1024;

  function compressImage(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        var scale = Math.min(1, MAX_DIMENSION / Math.max(img.width, img.height));
        var canvas = document.createElement('canvas');
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          if (!blob) { reject(new Error('toBlob failed')); return; }
          resolve(new File([blob], 'photo.jpg', { type: 'image/jpeg' }));
        }, 'image/jpeg', JPEG_QUALITY);
      };
      img.onerror = function () {
        URL.revokeObjectURL(url);
        reject(new Error('image decode failed'));
      };
      img.src = url;
    });
  }

  document.addEventListener('change', function (e) {
    var input = e.target;
    if (!input.matches || !input.matches('input[type="file"][name="attachment"]')) return;
    var file = input.files && input.files[0];
    if (!file || file.type === 'application/pdf' || file.type.indexOf('image/') !== 0) return;
    if (file.size < SKIP_BELOW_BYTES) return;

    compressImage(file).then(function (compressed) {
      if (compressed.size >= file.size) return;
      var dt = new DataTransfer();
      dt.items.add(compressed);
      input.files = dt.files;
    }).catch(function () {
      // keep the original file
    });
  });
})();
