/**
 * Set and remember tabs based upon hash value
 */

$().ready(function() {
    var active_tab = null;

    // Load tab contents when selected
    $("a[data-toggle='tab']").on('shown.bs.tab', function (e) {
        var target = $(e.target).attr("href");
        var url = $(e.target).attr("data");
        if (url !== undefined & url != '#' & $(target).is(':empty')) {
            $.ajax({
                type: "GET",
                url: url,
                error: function(request, status, error) {
                    var timestamp = new Date().getTime();
                    $(target).html('<div class="alert alert-danger">There was a problem!  <a href="?t='+timestamp+target+'">Refresh the page</a> or try again later.<br>'+request.status+' '+error+' (<a href="'+url+'">'+url+'</a>)</div>');
                },
                success: function(data){
                    $(target).html(data);
                }
            });
        }

        var tab_id = $(e.target).attr("href").substr(1);
        var hash = window.location.hash;
        if(hash[0] == '#') {
            hash = hash.substring(1);
        }
        if (hash == '') {
            location.replace('#!'+tab_id);
        } else {
            if (hash != '!'+tab_id) {
                window.location = '#!'+tab_id;
            }
        }

        active_tab = hash;
    })

    // Make tabs clickable
    $('#content-tabs a').click(function (e) {
        e.preventDefault()
        $(this).tab('show')
    });

    // Listen for hash changes, update shown tab if necessary
    function hashChangeEvent() {
        var hash = window.location.hash;
        if(hash[0] == '#') {
            hash = hash.substring(1);
        }
        var target = hash.substr(1);
        $("a[href='#" + hash.substr(1) + "']").tab("show");
    }
    window.onhashchange = hashChangeEvent;

    // Load first tab
    var hash = window.location.hash;
    if(hash[0] == '#') {
        hash = hash.substring(1);
    }
    if(hash == '') {
        default_tab = $('#content-tabs li a:first').attr('href');
        $('#content-tabs a[href="'+default_tab+'"]').tab('show');
    } else if(hash[0] == '!') {
        $("a[href='#" + hash.substr(1) + "']").tab("show");
    }
});
