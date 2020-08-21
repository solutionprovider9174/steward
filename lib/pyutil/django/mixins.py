# Django
from django.http import JsonResponse
from django.forms import BaseFormSet, formset_factory
from django.forms.models import model_to_dict
from django.views.generic.edit import FormMixin
from django.core.exceptions import ImproperlyConfigured
from django.views.generic.detail import SingleObjectTemplateResponseMixin


class JSONResponseMixin(object):
    """
    A mixin that can be used to render a JSON response.
    """
    def render_to_response(self, context, **response_kwargs):
        """
        Returns a JSON response, transforming 'context' to make the payload.
        """
        return JsonResponse(
            self.get_data(context),
            **response_kwargs
        )

    def get_data(self, context):
        """
        Returns an object that will be serialized as JSON by json.dumps().
        """
        # Note: This is *EXTREMELY* naive; in reality, you'll need
        # to do much more complex handling to ensure that arbitrary
        # objects -- such as Django model instances or querysets
        # -- can be serialized as JSON.
        return context

class JSONModelMixin(object):
    """
    A mixin that can be used to render a Model as a JSON response.
    """
    def render_to_response(self, context):
        if self.request.is_ajax() or self.request.GET.get('format') == 'json':
            return JSONResponseMixin.render_to_response(self, model_to_dict(self.get_object()))
        else:
            return SingleObjectTemplateResponseMixin.render_to_response(self, context)


class ProcessFormMixin(FormMixin):
    """
    Handles POST requests, instantiating a form instance with the passed
    POST variables and then checked for validity.
    """
    formset_class = None
    formset_extra = 0

    def get_formset_class(self):
        return self.formset_class

    def form_invalid(self, form, formset):
        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def get_formset(self, formset_class=None, formset_extra=None):
        if formset_class is None:
            formset_class = self.get_formset_class()
        if formset_extra is None:
            formset_extra = self.formset_extra
        if formset_class is None:
            return None
        else:
            formset = formset_factory(formset_class, extra=formset_extra)
            return formset(**self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        return super(ProcessFormMixin, self).get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()
        if formset:
            if form.is_valid() and formset.is_valid():
                return self.form_valid(form, formset)
        else:
            if form.is_valid():
                return self.form_valid(form, None)
