$.fn.digits = function(){
  return this.each(function(){
    $(this).text( $(this).text().replace(/(\d)(?=(\d\d\d)+(?!\d))/g, "$1,") );
  })
}

var qs = (function(a) {
  if (a == "") return {};
  var b = {};
  for (var i = 0; i < a.length; ++i) {
    var p=a[i].split('=', 2);
    if (p.length == 1) {
      b[p[0]] = "";
    } else {
      b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
    }
  }
  return b;
})(window.location.search.substr(1).split('&'));


function csrfSafeMethod(method) {
  // these HTTP methods do not require CSRF protection
  return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}
$.ajaxSetup({
  beforeSend: function(xhr, settings) {
    if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
      xhr.setRequestHeader("X-CSRFToken", Cookies.get('csrftoken'));
    }
  }
});
