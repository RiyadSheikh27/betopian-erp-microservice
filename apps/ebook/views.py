import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.response import APIResponse
from .models import EbookTitle, Ebook
from .serializers import EbookTitleSerializer, EbookSerializer

logger = logging.getLogger("apps.ebook")


class EbookTitleListView(APIView):
    """
    GET /ebook-titles/  - list all ebook titles.
    Query params: search - filter by ebook_title (partial, case-insensitive).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = EbookTitle.objects.all()

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(ebook_title__icontains=search)

        return APIResponse.success(data=EbookTitleSerializer(qs, many=True).data)


class EbookListView(APIView):
    """
    GET /ebooks/  - list all ebooks.
    Query params:
      search   - filter by title name (partial, case-insensitive).
      title_id - filter by exact EbookTitle id.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Ebook.objects.select_related("title")

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(title__ebook_title__icontains=search)

        title_id = request.query_params.get("title_id", "").strip()
        if title_id:
            qs = qs.filter(title_id=title_id)

        return APIResponse.success(
            data=EbookSerializer(qs, many=True, context={"request": request}).data
        )
