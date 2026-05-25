import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.response import APIResponse
from .models import EbookTitle, Ebook
from .serializers import EbookTitleSerializer, EbookSerializer
from django.db.models import Q

logger = logging.getLogger("apps.ebook")


class EbookTitleListView(APIView):
    """
    Query params: search - filter by category_title (partial, case-insensitive).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = EbookTitle.objects.all()

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(category_title__icontains=search)

        return APIResponse.success(
            data=EbookTitleSerializer(qs, many=True, context={"request": request}).data
        )


class EbookListView(APIView):
    """
    GET /ebooks/
    Query params:
      search- filter by file_name or category title (partial, case-insensitive).
      category_id - filter by exact EbookTitle id.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Ebook.objects.select_related("category").all()

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(file_name__icontains=search)
                | Q(category__category_title__icontains=search)
            )

        category_id = request.query_params.get("category_id", "").strip()
        if category_id:
            qs = qs.filter(category_id=category_id)

        return APIResponse.success(
            data=EbookSerializer(qs, many=True, context={"request": request}).data
        )
