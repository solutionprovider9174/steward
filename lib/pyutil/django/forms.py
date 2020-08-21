from django import forms
from django.db import models


class NullCharField(forms.fields.CharField):
    def clean(self, value):
        value = super(NullCharField, self).clean(value)
        if value in forms.fields.EMPTY_VALUES:
            value = None
        else:
            value = value.upper()
        return value
