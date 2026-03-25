from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Chapter
from .serializers import ChapterSerializer


class ChapterListView(generics.ListAPIView):
    queryset = Chapter.objects.filter(published=True)
    serializer_class = ChapterSerializer
    permission_classes = [AllowAny]


class ChapterDetailView(generics.RetrieveAPIView):
    queryset = Chapter.objects.filter(published=True)
    serializer_class = ChapterSerializer
    permission_classes = [AllowAny]
