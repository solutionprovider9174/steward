# Django
from django.conf import settings
from django import forms

# App
from deploy.models import Site, Device

# Third Party
from lib.pyutil.util import Util
from lib.pybw.broadworks import BroadWorks, Nil


class SiteCreateForm(forms.ModelForm):

    def clean(self):
        cleaned_data = super(SiteCreateForm, self).clean()
        provider_id = cleaned_data.get('provider_id')
        group_id = cleaned_data.get('group_id')

        try:
            bw = BroadWorks(**settings.PLATFORMS['broadworks'])
            bw.LoginRequest14sp4()
            resp0 = bw.GroupGetRequest14sp7(provider_id, group_id)
            data = resp0['data']
            if 'groupName' in data:
                cleaned_data['name'] = data['groupName']
            else:
                cleaned_data['name'] = ''
            if 'address' in data:
                if 'addressLine1' in data['address']:
                    cleaned_data['address_line1'] = data['address']['addressLine1']
                else:
                    cleaned_data['address_line1'] = ''
                if 'addressLine2' in data['address']:
                    cleaned_data['address_line2'] = data['address']['addressLine2']
                else:
                    cleaned_data['address_line2'] = ''
                if 'city' in data['address']:
                    cleaned_data['city'] = data['address']['city']
                else:
                    cleaned_data['city'] = ''
                if 'stateOrProvince' in data['address']:
                    cleaned_data['state'] = data['address']['stateOrProvince']
                else:
                    cleaned_data['state'] = ''
                if 'zipOrPostalCode' in data['address']:
                    cleaned_data['zip_code'] = data['address']['zipOrPostalCode']
                else:
                    cleaned_data['zip_code'] = ''
            bw.LogoutRequest()
        except Exception(e):
            raise ValidationError(e)
        return cleaned_data

    class Meta:
        model = Site
        fields = ['provider_id', 'group_id', 'name', 'address_line1', 'address_line2', 'city', 'state', 'zip_code']
        widgets = {
             'name': forms.HiddenInput(),
             'address_line1': forms.HiddenInput(),
             'address_line2': forms.HiddenInput(),
             'city': forms.HiddenInput(),
             'state': forms.HiddenInput(),
             'zip_code': forms.HiddenInput(),
        }


class SiteActionForm(forms.Form):
    ACTION_SYNC = 1
    CHOICES_ACTION = (
        (ACTION_SYNC, 'Sync'),
    )
    action = forms.TypedChoiceField(choices=CHOICES_ACTION, coerce=int, widget=forms.HiddenInput())


class DeviceUpdateForm(forms.ModelForm):
    state = forms.IntegerField(required=False)

    class Meta:
        model = Device
        fields = ('serial', 'device_type', 'state',)
