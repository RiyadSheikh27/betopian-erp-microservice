from django.urls import path
from apps.authentication.views import ProfileView, LogoutView
from apps.contents.views import (
    PostListCreateView,
    PostDetailView,
    ReelListCreateView,
    ReelDetailView,
    ReelViewCountView,
)
from apps.feed.views import PostNewsFeedView, ReelNewsFeedView

auth_urlpatterns = [
    # Authentication
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("profile/", ProfileView.as_view(), name="auth-profile"),
]

contents_urlpatterns = [
    # Posts
    path("posts/", PostListCreateView.as_view(), name="post-list-create"),
    path("posts/<uuid:pk>/", PostDetailView.as_view(), name="post-detail"),
    # Reels
    path("reels/", ReelListCreateView.as_view(), name="reel-list-create"),
    path("reels/<uuid:pk>/", ReelDetailView.as_view(), name="reel-detail"),
    path("reels/<uuid:pk>/view/", ReelViewCountView.as_view(), name="reel-view-count"),
]

feed_urlpatterns = [
    # News feed
    path("feed/posts/", PostNewsFeedView.as_view(), name="feed-posts"),
    path("feed/reels/", ReelNewsFeedView.as_view(), name="feed-reels"),
]


urlpatterns = [
    *auth_urlpatterns,
    *contents_urlpatterns,
    *feed_urlpatterns,
]
