from django.urls import path
from apps.authentication.views import ProfileView, LogoutView
from apps.contents.views import (
    PostListCreateView,
    PostDetailView,
    ReelListCreateView,
    ReelDetailView,
    ReelViewCountView,
    CommunityListView,
    CommunityMemberListView,
    SaveToggleView,
    SavedItemListView
)
from apps.feed.views import CommunityPostFeedView, PostNewsFeedView, ReelNewsFeedView
from apps.interactions.views import (
    LikeToggleView, 
    LikerListView, 
    CommentListCreateView, 
    CommentDetailView,
)
from apps.utils.views import ProfileImageUploadView
from apps.mom.views import (
    GeneralNoteListCreateView, GeneralNoteDetailView, GeneralNotePinToggleView,
    MeetingListCreateView, MeetingDetailView, MeetingPinToggleView,
    AgendaItemCreateView, AgendaItemDetailView,
    MeetingNoteCreateView, MeetingNoteDetailView, MeetingNotePinToggleView,
    MeetingParticipantView,
    NotesTabView,
)
from apps.ebook.views import EbookTitleListView, EbookListView

utils_urlpatterns = [
    path("upload-profile-image/", ProfileImageUploadView.as_view(), name="upload-profile-image"),
]

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
    path("communities/", CommunityListView.as_view(), name="community-list"),
    path("communities/<uuid:community_id>/members/", CommunityMemberListView.as_view(), name="community-members"),
    path("save/<str:target_type>/<uuid:pk>/", SaveToggleView.as_view(),   name="save-toggle"),
    path("saved/", SavedItemListView.as_view(), name="saved-list"),
]

feed_urlpatterns = [
    # News feed
    path("feed/posts/", PostNewsFeedView.as_view(), name="feed-posts"),
    path("feed/reels/", ReelNewsFeedView.as_view(), name="feed-reels"),
    path("feed/community/<uuid:community_id>/", CommunityPostFeedView.as_view(), name="feed-community-posts"), 
]

interactions_urlpatterns = [
    # Likes
    path("like/<str:target_type>/<uuid:pk>/", LikeToggleView.as_view(), name="like-toggle"),
    path("likers/<str:target_type>/<uuid:pk>/", LikerListView.as_view(), name="liker-list"),
    # Comment
    path("comment/<str:target_type>/<uuid:pk>/", CommentListCreateView.as_view(), name="comment-list-create"),
    path("comment/<str:target_type>/<uuid:pk>/<uuid:comment_id>/", CommentDetailView.as_view(), name="comment-detail"),
]

mom_urlpatterns = [
    # General notes
    path("notes/", GeneralNoteListCreateView.as_view(), name="mom-note-list-create"),
    path("notes/<uuid:pk>/", GeneralNoteDetailView.as_view(), name="mom-note-detail"),
    path("notes/<uuid:pk>/pin/", GeneralNotePinToggleView.as_view(), name="mom-note-pin"),

    # Meetings
    path("meetings/", MeetingListCreateView.as_view(), name="mom-meeting-list-create"),
    path("meetings/<uuid:pk>/", MeetingDetailView.as_view(), name="mom-meeting-detail"),
    path("meetings/<uuid:pk>/pin/", MeetingPinToggleView.as_view(), name="mom-meeting-pin"),

    # Participants
    path("meetings/<uuid:pk>/participants/", MeetingParticipantView.as_view(), name="mom-meeting-participants-add"),
    path("meetings/<uuid:pk>/participants/<int:central_id>/", MeetingParticipantView.as_view(), name="mom-meeting-participants-remove"),

    # Agenda items
    path("meetings/<uuid:pk>/agenda/", AgendaItemCreateView.as_view(), name="mom-agenda-create"),
    path("meetings/<uuid:pk>/agenda/<uuid:item_id>/", AgendaItemDetailView.as_view(), name="mom-agenda-detail"),

    # Meeting notes
    path("meetings/<uuid:pk>/notes/", MeetingNoteCreateView.as_view(), name="mom-meeting-note-create"),
    path("meetings/<uuid:pk>/notes/<uuid:note_id>/", MeetingNoteDetailView.as_view(), name="mom-meeting-note-detail"),
    path("meetings/<uuid:pk>/notes/<uuid:note_id>/pin/", MeetingNotePinToggleView.as_view(), name="mom-meeting-note-pin"),

    # Notes tab
    path("notes-tab/", NotesTabView.as_view(), name="mom-notes-tab"),
]


ebook_urlpatterns = [
    path("ebook-titles/", EbookTitleListView.as_view(), name="ebook-title-list"),
    path("ebooks/", EbookListView.as_view(), name="ebook-list"),
]
 
urlpatterns = [
    *auth_urlpatterns,
    *contents_urlpatterns,
    *feed_urlpatterns,
    *interactions_urlpatterns,
    *utils_urlpatterns,
    *mom_urlpatterns,
    *ebook_urlpatterns,
]
