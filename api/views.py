from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


class RootAPIView(APIView):

    def get(self, request, format=None):
        context = {
            'routing': reverse('api:routing-root', request=request, format=format),
            'tools': reverse('api:tools-root', request=request, format=format),
        }
        return Response(context)
