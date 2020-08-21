$().ready(function() {

  function update_fields() {
    if ($('#id_action_type').val() == 'System') {
      $('#id_submit').removeClass('disabled');
      $('#id_provider_id').parent().addClass('hidden');
      $('#id_group_id').parent().addClass('hidden');
    } else if ($('#id_action_type').val() == 'Provider/Group') {
      $('#id_submit').removeClass('disabled');
      $('#id_provider_id').parent().removeClass('hidden');
      $('#id_group_id').parent().removeClass('hidden');
    } else {
        $('#id_submit').addClass('disabled');
        $('#id_provider_id').parent().addClass('hidden');
        $('#id_group_id').parent().addClass('hidden');
    }
  };

  update_fields();
  $('#id_action_type').on('change', function() {
    update_fields();
  });
});
