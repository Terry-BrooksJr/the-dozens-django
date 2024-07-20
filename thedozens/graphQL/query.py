from API.filters import InsultFilter
from API.models import Insult
from graphene import ID, Boolean, Field, List, ObjectType, String
from graphene_django import DjangoObjectType

# Create your views here.


class InsultType(DjangoObjectType):
    class Meta:
        name = "Insult"
        description = "The GraphQL Object Type for Insult Catagory"
        model = Insult
        field = (
            "content",
            "category",
            "explicit",
            "added_on",
            "added_by",
            "last_modified",
            "status",
        )
        filterset_class = InsultFilter


class Query(ObjectType):
    random_insult = Field(InsultType)
    insult_by_category = List(InsultType, category=String())
    insults_by_status = Field(InsultType, status=String())
    insults_by_classification = Field(InsultType, explicit=Boolean())
    insult_by_id = Field(InsultType, id=ID())

    def resolve_insults(root, info, **kwargs):
        # sourcery skip: instance-method-first-arg-name
        return Insult.objects.fiter(status="A")

    def resolve_insult_by_category(root, info, category):
        # sourcery skip: instance-method-first-arg-name
        return Insult.objects.fiter(status="A").filter(category=category)

    def resolve_insults_by_status(root, info, status):
        # sourcery skip: instance-method-first-arg-name
        return Insult.objects.filter(status=status)

    def resolve_insults_by_classification(root, info, explicit):
        # sourcery skip: instance-method-first-arg-name
        return Insult.objects.filter(explicit=explicit)

    def resolve_insult_by_id(root, info, pk):
        # sourcery skip: instance-method-first-arg-name
        return Insult.objects.get(id=pk)
