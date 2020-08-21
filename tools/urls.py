from django.urls import re_path

# Application
import tools.views

app_name ='tools'
urlpatterns = [
    re_path(r'^$', tools.views.IndexView.as_view(), name='index'),
    # Tools
    re_path(r'^call-park-pickup-configurator$', tools.views.CallParkPickupConfiguratorToolView.as_view(), name='call-park-pickup-configurator'),
    re_path(r'^dect-configurator$', tools.views.DectConfiguratorToolView.as_view(), name='dect-configurator'),
    re_path(r'^device-specific-migration-tool$', tools.views.DeviceSpecificMigrationToolView.as_view(), name='device-specific-migration-tool'),
    re_path(r'^fraud-compliance-reset-tool$', tools.views.FraudComplianceResetToolView.as_view(), name='fraud-compliance-reset-tool'),
    re_path(r'^lab-rebuild-tool$', tools.views.LabResetToolView.as_view(), name='lab-rebuild-tool'),
    re_path(r'^push-to-talk-configurator$', tools.views.PushToTalkConfiguratorToolView.as_view(), name='push-to-talk-configurator'),
    re_path(r'^tag-removal$', tools.views.TagRemovalToolView.as_view(), name='tag-removal'),
    re_path(r'^speed-dial-configurator$', tools.views.SpeedDialConfiguratorToolView.as_view(), name='speed-dial-configurator'),
    re_path(r'^trunk-user-audit$', tools.views.TrunkAuditToolView.as_view(), name='trunk-user-audit'),
    re_path(r'^blf-fixup$', tools.views.BusyLampFieldFixupToolView.as_view(), name='busy-lamp-field-fixup'),
    # Reports
    re_path(r'^firmware-report$', tools.views.FirmwareReportView.as_view(), name='firmware-report'),
    re_path(r'^registrations-report$', tools.views.RegistrationReportView.as_view(), name='registrations-report'),
    re_path(r'^registration-by-type-report$', tools.views.RegistrationByTypeReportView.as_view(), name='registration-by-type-report'),
    re_path(r'^tag-report$', tools.views.TagReportView.as_view(), name='tag-report'),
    # Results
    re_path(r'^jobs/$', tools.views.ProcessListView.as_view(), name='process-list'),
    re_path(r'^results/(?P<pk>\d+)/$', tools.views.ProcessDetailView.as_view(), name='process-detail'),
]
