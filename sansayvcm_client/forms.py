#django
from django import forms

#local
from .models import SansayVcmServer, SansayCluster

class SansayVcmServerForm(forms.Form):
    server = forms.ModelChoiceField(label="Sansay Server", widget=forms.Select(attrs={'class': 'form-control'}), queryset=SansayVcmServer.objects.all())

class ModifyRouteTableForm(SansayVcmServerForm):
    cluster = forms.ModelChoiceField(label="Cluster", widget=forms.Select(attrs={'class': 'form-control'}), queryset=SansayCluster.objects.all())
    did = forms.CharField(label='Routing DID', max_length=10, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))

