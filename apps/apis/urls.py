from django.urls import path
from apps.authentication.views import (
    ProfileView,
    LogoutView,
    SSOLoginView,
    ResolveEmployeeIdView,
)
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
from apps.feed.views import CommunityPostFeedView, PostNewsFeedView, ReelNewsFeedView, FeedPostDetailView
from apps.interactions.views import (
    LikeToggleView, 
    LikerListView, 
    CommentListCreateView, 
    CommentDetailView,
)
from apps.notifications.views import (
    NotificationListView,
    NotificationUnreadCountView,
    NotificationReadAllView,
    NotificationReadView,
    NotificationDeleteView,
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
from apps.chat.views import (
    UserSearchView,
    ConversationListView,
    ConversationParticipantsView,
    MessageListView,
    MessageReactionListView,
    ConversationMediaView,
    TurnCredentialsView,
    CallInitiateView,
    CallDetailView,
    CallAcceptView,
    CallDeclineView,
    CallCancelView,
    CallConnectedView,
    CallEndView,
)
from apps.notifications.views import DeviceRegisterView, DeviceUnregisterView
from apps.story.views import (
    StoryTrayView,
    StoryUserCarouselView,
    StoryCreateView,
    StoryViewMarkView,
    StoryDeleteView,
    StoryMineView,
    StoryViewersView,
)
    
utils_urlpatterns = [
    path("upload-profile-image/", ProfileImageUploadView.as_view(), name="upload-profile-image"),
]

auth_urlpatterns = [
    # Authentication
    path("login/", SSOLoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("profile/", ProfileView.as_view(), name="auth-profile"),
    path(
        "resolve-employee-id/",
        ResolveEmployeeIdView.as_view(),
        name="auth-resolve-employee-id",
    ),
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
    path("feed/posts/<uuid:pk>/", FeedPostDetailView.as_view(), name="feed-post-detail"),
    path("feed/reels/", ReelNewsFeedView.as_view(), name="feed-reels"),
    path("feed/community/<uuid:community_id>/", CommunityPostFeedView.as_view(), name="feed-community-posts"), 
]

notification_urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/unread-count/", NotificationUnreadCountView.as_view(), name="notification-unread-count",),
    path("notifications/read-all/", NotificationReadAllView.as_view(), name="notification-read-all",),
    path("notifications/<uuid:pk>/read/", NotificationReadView.as_view(), name="notification-read",),
    path("notifications/<uuid:pk>/", NotificationDeleteView.as_view(), name="notification-delete",),
    path("devices/register/", DeviceRegisterView.as_view(), name="device-register"),
    path("devices/unregister/", DeviceUnregisterView.as_view(), name="device-unregister"),
]

interactions_urlpatterns = [
    # Likes
    path("react/<str:target_type>/<uuid:pk>/", LikeToggleView.as_view(), name="like-toggle"),
    path("reactors/<str:target_type>/<uuid:pk>/", LikerListView.as_view(), name="liker-list"),
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

chat_urlpatterns = [
    # User search (central ERP + local DB match)
    path("conversations/user/search/", UserSearchView.as_view(), name="chat-user-search"),

    # Conversation list + start DM
    path("conversations/", ConversationListView.as_view(), name="chat-conv-list"),

    # Participants list
    path("conversations/<uuid:conv_id>/participants/", ConversationParticipantsView.as_view(), name="chat-conv-participants"),

    # Message history + media upload
    path("conversations/<uuid:conv_id>/messages/", MessageListView.as_view(), name="chat-messages"),

    # Reaction list (who reacted with what)
    path("conversations/<uuid:conv_id>/messages/<uuid:msg_id>/reactions/", MessageReactionListView.as_view(), name="chat-reactions"),

    # Shared media gallery
    path("conversations/<uuid:conv_id>/media/", ConversationMediaView.as_view(), name="chat-media"),

    path("turn-credentials/", TurnCredentialsView.as_view(), name="turn-credentials"),

    # 1:1 voice/video calls (WhatsApp-style — REST lifecycle + dedicated WS for WebRTC)
    path("calls/initiate/", CallInitiateView.as_view(), name="call-initiate"),
    path("calls/<uuid:call_id>/", CallDetailView.as_view(), name="call-detail"),
    path("calls/<uuid:call_id>/accept/", CallAcceptView.as_view(), name="call-accept"),
    path("calls/<uuid:call_id>/decline/", CallDeclineView.as_view(), name="call-decline"),
    path("calls/<uuid:call_id>/cancel/", CallCancelView.as_view(), name="call-cancel"),
    path("calls/<uuid:call_id>/connected/", CallConnectedView.as_view(), name="call-connected"),
    path("calls/<uuid:call_id>/end/", CallEndView.as_view(), name="call-end"),
]

story_urlpatterns = [
    path("stories/tray/", StoryTrayView.as_view(), name="story-tray"),
    path("stories/mine/", StoryMineView.as_view(), name="story-mine"),
    path("stories/user/<uuid:user_id>/", StoryUserCarouselView.as_view(), name="story-user-carousel"),
    path("stories/<uuid:pk>/view/", StoryViewMarkView.as_view(), name="story-view"),
    path("stories/<uuid:pk>/viewers/", StoryViewersView.as_view(), name="story-viewers"),
    path("stories/<uuid:pk>/", StoryDeleteView.as_view(), name="story-delete"),
    path("stories/", StoryCreateView.as_view(), name="story-create"),
]

urlpatterns = [
    *auth_urlpatterns,
    *contents_urlpatterns,
    *feed_urlpatterns,
    *notification_urlpatterns,
    *interactions_urlpatterns,
    *utils_urlpatterns,
    *mom_urlpatterns,
    *ebook_urlpatterns,
    *chat_urlpatterns,
    *story_urlpatterns,
]
