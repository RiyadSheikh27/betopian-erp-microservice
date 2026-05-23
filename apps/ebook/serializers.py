from rest_framework import serializers
from .models import EbookTitle, Ebook


class EbookTitleSerializer(serializers.ModelSerializer):
    category_image = serializers.SerializerMethodField()

    class Meta:
        model = EbookTitle
        fields = ("id", "category_title", "category_image", "created_at")
        read_only_fields = ("id", "created_at")

    def get_category_image(self, obj):
        request = self.context.get("request")
        if obj.category_image and request:
            return request.build_absolute_uri(obj.category_image.url)
        return None


class EbookSerializer(serializers.ModelSerializer):
    category = EbookTitleSerializer(read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = Ebook
        fields = ("id", "category", "file_name", "url", "created_at")
        read_only_fields = ("id", "created_at")

    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url
