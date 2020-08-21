# Django
from django.db import models
from django.utils.text import capfirst

# Application
from . import forms

class NullCharField(models.CharField):

    def formfield(self, form_class=None, choices_form_class=None, **kwargs):
        """
        Returns a django.forms.Field instance for this database Field.
        Does not handle choices
        """
        defaults = {'required': not self.blank,
                    'label': capfirst(self.verbose_name),
                    'help_text': self.help_text}
        if self.has_default():
            if callable(self.default):
                defaults['initial'] = self.default
                defaults['show_hidden_initial'] = True
            else:
                defaults['initial'] = self.get_default()
        defaults.update(kwargs)
        if form_class is None:
            form_class = forms.NullCharField
        return form_class(**defaults)
