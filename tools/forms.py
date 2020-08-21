# django
from django import forms
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.validators import MinLengthValidator, RegexValidator
# local
from platforms.models import BroadworksPlatform


class BroadworksPlatformForm(forms.Form):
    platform = forms.ModelChoiceField(label="Platform", queryset=BroadworksPlatform.objects.all())


class TypedProviderGroupForm(BroadworksPlatformForm):
    PROVIDER_TYPE_CHOICE_ENTERPRISE = 'Enterprise'
    PROVIDER_TYPE_CHOICE_SERVICE_PROVIDER = 'Service Provider'
    PROVIDER_TYPE_CHOICES = (
        ('', '----'),
        (PROVIDER_TYPE_CHOICE_ENTERPRISE, PROVIDER_TYPE_CHOICE_ENTERPRISE),
        (PROVIDER_TYPE_CHOICE_SERVICE_PROVIDER, PROVIDER_TYPE_CHOICE_SERVICE_PROVIDER),
    )
    provider_type = forms.ChoiceField(label='Provider Type', choices=PROVIDER_TYPE_CHOICES, required=True)
    provider_id = forms.CharField(label='Provider Id', max_length=256, required=True)
    group_id = forms.CharField(label='Group Id', max_length=256, required=False)

    javascript = static('tools/provider_group_form.js')

    def clean(self):
        cleaned_data = super(TypedProviderGroupForm, self).clean()
        provider_type = cleaned_data.get("provider_type")
        provider_id = cleaned_data.get("provider_id")
        group_id = cleaned_data.get("group_id")

        if provider_type == self.PROVIDER_TYPE_CHOICE_ENTERPRISE:
            if not provider_id:
                raise forms.ValidationError("Provider Id is required")
        elif provider_type == self.PROVIDER_TYPE_CHOICE_SERVICE_PROVIDER:
            if not provider_id or not group_id:
                raise forms.ValidationError("Provider Id and Group Id is required")
        else:
            raise forms.ValidationError("Invalid provider type")
        return cleaned_data


class CallParkPickupForm(TypedProviderGroupForm):
    park = forms.BooleanField(label="Call Park", required=False, initial=True)
    retrieve = forms.BooleanField(label="Call Retrieve", required=False, initial=True)

    def clean(self):
        cleaned_data = super(CallParkPickupForm, self).clean()
        cleaned_data['park'] = str(cleaned_data.get("park", False))
        cleaned_data['retrieve'] = str(cleaned_data.get("retrieve", False))
        return cleaned_data

class ProviderGroupForm(BroadworksPlatformForm):
    provider_id = forms.CharField(label='Provider Id', max_length=256, required=True)
    group_id = forms.CharField(label='Group Id', max_length=256, required=False)


class SystemProviderGroupForm(BroadworksPlatformForm):
    ACTION_TYPE_CHOICE_SYSTEM = 'System'
    ACTION_TYPE_CHOICE_PROVIDER = 'Provider/Group'
    ACTION_TYPE_CHOICES = (
        ('', '----'),
        (ACTION_TYPE_CHOICE_SYSTEM, ACTION_TYPE_CHOICE_SYSTEM),
        (ACTION_TYPE_CHOICE_PROVIDER, ACTION_TYPE_CHOICE_PROVIDER),
    )
    action_type = forms.ChoiceField(label='Type', choices=ACTION_TYPE_CHOICES, required=True)
    provider_id = forms.CharField(label='Provider Id', max_length=256, required=False)
    group_id = forms.CharField(label='Group Id', max_length=256, required=False)

    javascript = static('tools/system_provider_group_form.js')


class TagReportForm(SystemProviderGroupForm):
    tag_names = forms.CharField(label='Tag Names', max_length=256, required=True)


class TagRemovalForm(TypedProviderGroupForm):
    tag_names = forms.CharField(label='Tag Names', max_length=256, required=True)


class TrunkUserAuditForm(BroadworksPlatformForm):
    fixup = forms.BooleanField(label="Fixup", required=False, initial=False)

    def clean(self):
        cleaned_data = super(TrunkUserAuditForm, self).clean()
        cleaned_data['fixup'] = str(cleaned_data.get("fixup", False))
        return cleaned_data


class SpeedDialLineForm(forms.Form):
    code = forms.CharField(max_length=2,
                           validators=[
                                RegexValidator(r'^\d{2}$', 'Enter a valid speed dial code.'),
                           ],
                           widget=forms.TextInput(attrs={'placeholder': 'Code', 'class': 'col-lg-1'}))
    description = forms.CharField(max_length=64,
                                  widget=forms.TextInput(attrs={'placeholder': 'Description', 'class': 'col-lg-4'}))
    destination_number = forms.CharField(max_length=64,
                                         validators=[
                                            RegexValidator(r'^\d{4,}$', 'Enter a valid speed dial destination number.'),
                                         ],
                                         widget=forms.TextInput(attrs={'placeholder': 'Destination Number', 'class': 'col-lg-6'}))


class DeviceForm(BroadworksPlatformForm):
    provider_id = forms.CharField(label='Provider Id', max_length=256, required=True)
    group_id = forms.CharField(label='Group Id', max_length=256, required=True)
    device_name = forms.CharField(label='Device Name', max_length=256, required=True)


class DectLineForm(forms.Form):
    handset = forms.IntegerField(required=True, widget=forms.NumberInput(attrs={'placeholder': 'Handset', 'class': 'col-lg-1'}))
    line = forms.IntegerField(required=True, widget=forms.NumberInput(attrs={'placeholder': 'Line', 'class': 'col-lg-1'}))
    user_id = forms.CharField(max_length=64, required=True, widget=forms.TextInput(attrs={'placeholder': 'User Id', 'class': 'col-lg-5'}))
    lineport = forms.CharField(max_length=128, required=False, widget=forms.TextInput(attrs={'placeholder': 'Line Port', 'class': 'col-lg-4', 'disabled': True}))


class BusyLampFieldFixupForm(ProviderGroupForm):
    pass


class EmptyForm(BroadworksPlatformForm):
    pass
