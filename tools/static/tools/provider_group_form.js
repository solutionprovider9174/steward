function update_fields() {
  if ($('#id_provider_type').val() == 'Enterprise') {
    $('#id_submit').removeClass('disabled');
    $('#id_provider_id').parent().removeClass('hidden');
    $('#id_group_id').parent().removeClass('hidden');
  } else if ($('#id_provider_type').val() == 'Service Provider') {
    $('#id_submit').removeClass('disabled');
    $('#id_provider_id').parent().removeClass('hidden');
    $('#id_group_id').parent().removeClass('hidden');
  } else {
      $('#id_submit').addClass('disabled');
      $('#id_provider_id').parent().addClass('hidden');
      $('#id_group_id').parent().addClass('hidden');
  }
};

$().ready(function() {
  update_fields();
  $('#id_provider_type').on('change', function() {
    update_fields();
  });
});
