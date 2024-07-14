import random
<<<<<<< Updated upstream
from rest_framework.decorators import api_view, renderer_classes, permission_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.permissions import AllowAny

RANDOM_QS = Insult.objects.filter(status="A").values("id", "content").cache(ops=["get"])


@api_view(["GET"])
@permission_classes([AllowAny])
@renderer_classes((JSONRenderer, TemplateHTMLRenderer))
def randomUnfilteredInsult(request):
    queryset = list(RANDOM_QS)
    return Response(data=random.choice(seq=queryset), status=status.HTTP_200_OK)


class InsultsView(ListAPIView):
=======

from drf_spectacular.utils import extend_schema, OpenApiParameter
from API.filters import InsultFilter
from API.models import Insult
from API.serializers import InsultsCategorySerializer, InsultSerializer, MyInsultSerializer
from django_filters import rest_framework as filters
from rest_framework.response import Response

from rest_framework.views import APIView, status

from rest_framework.generics import (ListAPIView, RetrieveAPIView,
                                     RetrieveUpdateDestroyAPIView)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
class InsultMe(RetrieveAPIView):
    serializer_class = InsultSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        nsfw = self.request.get('')
        category = None

        queryset = queryset # TODO
        return queryset

class InsultCatergories(APIView):
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        categories = Insult.CATEGORY.choices
        display_name = []
        for category in  categories:
            display_name.append(category[1])
        return Response(display_name)
 
@extend_schema(parameters=[
    OpenApiParameter()
])
class InsultsCatergoriesListView(ListAPIView):
>>>>>>> Stashed changes
    queryset = Insult.objects.all()
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
    lookup_field = "category"
    serializer_class = InsultsCategorySerializer
<<<<<<< Updated upstream


=======
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]
    
    def get_queryset(self):
        category = self.kwargs['category']
        category = category.lower()
        available_categories = dict((y, x) for x, y in Insult.CATEGORY.choices)
        available_categories = [[cat.lower()] for cat in available_categories]
        if category not in available_categories.keys():
                return None
        else:
            for key,value in available_categories.items():
                if key == category:
                    request_cat_code = available_categories[key]
                return Insult.objects.filter(status="A").filter(category=request_cat_code)
        
@extend_schema(request=InsultSerializer, responses=InsultSerializer)
>>>>>>> Stashed changes
class InsultSingleItem(RetrieveAPIView):
    queryset = Insult.objects.all()
    lookup_field = "id"
    serializer_class = InsultSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsultFilter
<<<<<<< Updated upstream
    serializer_class = InsultSerializer


=======
    permission_classes = [AllowAny]
    
@extend_schema(request=InsultSerializer, responses=MyInsultSerializer)
>>>>>>> Stashed changes
class MyInsultsView(RetrieveUpdateDestroyAPIView):
    def get_queryset(self):
        """
        This view returns a list of all insults created by the currently
        authenticated user.

        Returns empty list if user Anonymous
        """
        user = self.request.user

        if not user.is_anonymous:
            return Insult.objects.filter(added_by=user)

        return Insult.objects.none()
