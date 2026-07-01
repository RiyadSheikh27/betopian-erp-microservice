# Contents API Documentation

## Base URL
```
http://localhost:8000/api/
```

## Authentication
All endpoints require JWT token authentication. Include the token in the request header:
```
Authorization: Bearer <access_token>
```

---

## Posts API

### 1. List User's Posts
**Endpoint:** `GET /posts/`

**Authentication:** Required

**Description:** Retrieve all posts created by the authenticated user with cursor-based pagination.

**Query Parameters:**
- `page_size` (optional, default: 10, max: 50) - Number of items per page
- `cursor` (optional) - Pagination cursor from previous response

**Response (200 OK):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "author": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "username": "john_doe",
        "full_name": "John Doe",
        "designation": "Software Engineer",
        "branch": "Engineering",
        "avatar": "http://localhost:8000/media/avatars/user.jpg"
      },
      "caption": "My first post!",
      "privacy": "public",
      "is_edited": false,
      "media": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440002",
          "url": "http://localhost:8000/media/posts/2026/05/10/image1.jpg",
          "media_type": "image",
          "caption": "Photo caption",
          "order": 0
        }
      ],
      "media_count": 1,
      "created_at": "2026-05-10T10:30:00Z",
      "updated_at": "2026-05-10T10:30:00Z"
    }
  ],
  "meta": {
    "next_cursor": "MjAyNi0wNS0xMFQxMDozMDowMFo6OjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMQ==",
    "has_more": true,
    "page_size": 10
  }
}
```

**Error Responses:**
- `400 Bad Request` - Invalid cursor
- `401 Unauthorized` - Missing or invalid token

---

### 2. Create a Post
**Endpoint:** `POST /posts/`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Description:** Create a new post with optional media attachments.

**Request Body:**
```
caption (string, optional) - Post text content
privacy (string, optional) - "public" or "only_me" (default: "public")
files (file[], optional) - Array of image/video files
captions (string[], optional) - Captions for each file in same order
```

**Postman Form-Data Setup:**

In Postman, go to the **Body** tab and select **form-data**. Add the following fields:

| Key | Type | Value | Example |
|-----|------|-------|---------|
| `caption` | Text | Post text content | "Check out this post!" |
| `privacy` | Text | "public" or "only_me" | "public" |
| `files` | File | Image/Video file 1 | Select image1.jpg |
| `captions` | Text | Caption for file 1 | "First image" |
| `files` | File | Image/Video file 2 | Select video1.mp4 |
| `captions` | Text | Caption for file 2 | "Short video" |

**Important:** Each `files` entry must have a corresponding `captions` entry in the same order. The order matters!

**Steps in Postman:**
1. Set request method to **POST**
2. Enter URL: `http://localhost:8000/api/posts/`
3. Go to **Headers** tab - Add header:
   - Key: `Authorization`
   - Value: `Bearer <your_access_token>`
4. Go to **Body** tab - Select **form-data**
5. Add fields in order (important for matching captions to files):
   - `caption` (Text) - Post description
   - `privacy` (Text) - "public" or "only_me"
   - `files` (File) - First file
   - `captions` (Text) - Caption for first file
   - `files` (File) - Second file
   - `captions` (Text) - Caption for second file
   - etc.

**Step-by-step visual guide:**

| Step | Action | Key | Type | Value |
|------|--------|-----|------|-------|
| 1 | Add | caption | Text | "A day long tour to Sajek6" |
| 2 | Add | privacy | Text | "public" |
| 3 | Add | files | File | dummy.png (click Select Files) |
| 4 | Add | captions | Text | "Dummy image" |
| 5 | Add | files | File | sample_video.mp4 (click Select Files) |
| 6 | Add | captions | Text | "Sample video" |
| 7 | Add | files | File | profile.jpg (click Select Files) |
| 8 | Add | captions | Text | "Profile picture" |
| 9 | Click **Send** |

**Common Mistakes to Avoid:**
- ❌ Uploading files without captions (leave captions empty if you don't have text)
- ❌ Not matching the order of files and captions
- ❌ Using field names like `file1`, `file2` instead of `files`
- ❌ Using field names like `caption1`, `caption2` instead of `captions`

**To add empty captions:** If a file doesn't need a caption, just add an empty `captions` field (leave the Value field blank in Postman).

**Note:** When adding multiple files:
- Click the **"+"** button next to the fields to add more rows
- Keep the key as `files` for all files and `captions` for all captions
- Postman will automatically create multiple entries with the same key
- The order must match: file1, caption1, file2, caption2, etc.

**cURL Example:**
```bash
curl -X POST http://localhost:8000/api/posts/ \
  -H "Authorization: Bearer <access_token>" \
  -F "caption=A day long tour to Sajek6" \
  -F "privacy=public" \
  -F "files=@dummy.png" \
  -F "captions=Dummy image" \
  -F "files=@sample_video.mp4" \
  -F "captions=Sample video" \
  -F "files=@profile.jpg" \
  -F "captions=Profile picture"
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Post created successfully.",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "author": { ... },
    "caption": "Check out this post!",
    "privacy": "public",
    "is_edited": false,
    "media": [ ... ],
    "media_count": 2,
    "created_at": "2026-05-10T10:30:00Z",
    "updated_at": "2026-05-10T10:30:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request` - Invalid file type or validation errors
- `401 Unauthorized` - Missing or invalid token

**Supported File Types:**
- **Images:** JPEG, PNG, GIF, WebP
- **Videos:** MP4, MOV, AVI, WebM

**Troubleshooting:**

**Q: I uploaded files but media_count is 0 and media array is empty**
- A: You didn't include the `captions` field in your form-data. Add a `captions` field for each file, even if you leave it empty.

**Q: The captions don't match the right files**
- A: The order matters! Make sure files and captions are in the same order:
  ```
  files: dummy.png
  captions: Caption for dummy.png
  files: sample_video.mp4
  captions: Caption for sample_video.mp4
  ```

**Q: Getting validation error about unsupported file type**
- A: Check that your file format is supported (see Supported File Types above). Common issues:
  - Uploading `.webp` images without WebP support
  - Uploading `.mov` videos without QuickTime support
  - Uploading corrupted or wrong file extensions

---

### 3. Get Post Details
**Endpoint:** `GET /posts/{id}/`

**Authentication:** Required

**Description:** Retrieve a specific post by ID. Only the post author can access their own posts.

**Path Parameters:**
- `id` (string, required) - Post UUID

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "author": { ... },
    "caption": "My first post!",
    "privacy": "public",
    "is_edited": false,
    "media": [ ... ],
    "media_count": 1,
    "created_at": "2026-05-10T10:30:00Z",
    "updated_at": "2026-05-10T10:30:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found` - Post not found or not owned by user
- `401 Unauthorized` - Missing or invalid token

---

### 4. Update a Post
**Endpoint:** `PATCH /posts/{id}/`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Description:** Update post caption, privacy, or media. All fields are optional.

**Path Parameters:**
- `id` (string, required) - Post UUID

**Request Body:**
```
caption (string, optional) - Updated post text
privacy (string, optional) - "public" or "only_me"
add_files (file[], optional) - New files to attach
add_captions (string[], optional) - Captions for new files
remove_media_ids (uuid[], optional) - Media IDs to remove
edit_media_id (uuid[], optional) - Media IDs to update captions for
edit_media_caption (string[], optional) - New captions (positional matching)
```

**Postman Form-Data Setup:**

In Postman, go to the **Body** tab and select **form-data**. Add the following fields:

| Key | Type | Value | Example |
|-----|------|-------|---------|
| `caption` | Text | Updated post text (optional) | "Updated caption!" |
| `privacy` | Text | "public" or "only_me" (optional) | "only_me" |
| `add_files` | File | New image/video files to add | Select new_image.jpg |
| `add_captions` | Text | Captions for new files | "New photo" |
| `remove_media_ids` | Text | Media UUID to remove | "550e8400-e29b-41d4-a716-446655440002" |
| `edit_media_id` | Text | Media UUID to update caption | "550e8400-e29b-41d4-a716-446655440003" |
| `edit_media_caption` | Text | New caption for media | "Updated caption" |

**Steps in Postman:**
1. Set request method to **PATCH**
2. Enter URL: `http://localhost:8000/api/posts/{post_id}/` (replace {post_id} with actual UUID)
3. Go to **Headers** tab - Add header:
   - Key: `Authorization`
   - Value: `Bearer <your_access_token>`
4. Go to **Body** tab - Select **form-data**
5. Add only the fields you want to update:
   - **Text fields**: caption, privacy, remove_media_ids, edit_media_id, edit_media_caption
   - **File fields**: add_files
6. Click **Send**

**Notes:**
- All fields are optional - send only what you want to change
- For removing multiple media: Add multiple `remove_media_ids` rows with different UUIDs
- For editing multiple captions: Add multiple `edit_media_id` and `edit_media_caption` pairs (matched positionally)

**cURL Example:**
```bash
curl -X PATCH http://localhost:8000/api/posts/550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <access_token>" \
  -F "caption=Updated caption!" \
  -F "privacy=only_me" \
  -F "add_files=@new_image.jpg" \
  -F "add_captions=New photo" \
  -F "remove_media_ids=550e8400-e29b-41d4-a716-446655440002"
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Post updated successfully.",
  "data": { ... }
}
```

**Error Responses:**
- `400 Bad Request` - Invalid file type or media ID not found
- `404 Not Found` - Post not found
- `401 Unauthorized` - Missing or invalid token

---

### 5. Delete a Post
**Endpoint:** `DELETE /posts/{id}/`

**Authentication:** Required

**Description:** Delete a post and all its associated media.

**Path Parameters:**
- `id` (string, required) - Post UUID

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Post deleted successfully."
}
```

**Error Responses:**
- `404 Not Found` - Post not found
- `401 Unauthorized` - Missing or invalid token

---

## Reels API

### 1. List User's Reels
**Endpoint:** `GET /reels/`

**Authentication:** Required

**Description:** Retrieve all reels created by the authenticated user with cursor-based pagination.

**Query Parameters:**
- `page_size` (optional, default: 10, max: 50) - Number of items per page
- `cursor` (optional) - Pagination cursor from previous response

**Response (200 OK):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "author": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "username": "john_doe",
        "full_name": "John Doe",
        "designation": "Software Engineer",
        "branch": "Engineering",
        "avatar": "http://localhost:8000/media/avatars/user.jpg"
      },
      "caption": "My awesome reel!",
      "video_url": "http://localhost:8000/media/reels/2026/05/10/video1.mp4",
      "privacy": "public",
      "view_count": 150,
      "is_edited": false,
      "created_at": "2026-05-10T10:30:00Z",
      "updated_at": "2026-05-10T10:30:00Z"
    }
  ],
  "meta": {
    "next_cursor": "MjAyNi0wNS0xMFQxMDozMDowMFo6OjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMQ==",
    "has_more": true,
    "page_size": 10
  }
}
```

**Error Responses:**
- `400 Bad Request` - Invalid cursor
- `401 Unauthorized` - Missing or invalid token

---

### 2. Create a Reel
**Endpoint:** `POST /reels/`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Description:** Upload a new reel (single video + caption).

**Request Body:**
```
video (file, required) - Video file
caption (string, optional) - Reel description
privacy (string, optional) - "public" or "only_me" (default: "public")
```

**Postman Form-Data Setup:**

In Postman, go to the **Body** tab and select **form-data**. Add the following fields:

| Key | Type | Value | Example |
|-----|------|-------|---------|
| `video` | File | Video file (required) | Select reel_video.mp4 |
| `caption` | Text | Reel description (optional) | "Check out my reel!" |
| `privacy` | Text | "public" or "only_me" (optional) | "public" |

**Steps in Postman:**
1. Set request method to **POST**
2. Enter URL: `http://localhost:8000/api/reels/`
3. Go to **Headers** tab - Add header:
   - Key: `Authorization`
   - Value: `Bearer <your_access_token>`
4. Go to **Body** tab - Select **form-data**
5. Add fields:
   - **video** - Select "File" type, click "Select Files" and choose your video file
   - **caption** - Select "Text" type, enter your caption text
   - **privacy** - Select "Text" type, enter "public" or "only_me"
6. Click **Send**

**cURL Example:**
```bash
curl -X POST http://localhost:8000/api/reels/ \
  -H "Authorization: Bearer <access_token>" \
  -F "video=@reel_video.mp4" \
  -F "caption=Check out my reel!" \
  -F "privacy=public"
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Reel created successfully.",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "author": { ... },
    "caption": "Check out my reel!",
    "video_url": "http://localhost:8000/media/reels/2026/05/10/video1.mp4",
    "privacy": "public",
    "view_count": 0,
    "is_edited": false,
    "created_at": "2026-05-10T10:30:00Z",
    "updated_at": "2026-05-10T10:30:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request` - Invalid video format or missing required fields
- `401 Unauthorized` - Missing or invalid token

**Supported Video Formats:** MP4, MOV, AVI, WebM

---

### 3. Get Reel Details
**Endpoint:** `GET /reels/{id}/`

**Authentication:** Required

**Description:** Retrieve a specific reel by ID. Only the reel author can access their own reels.

**Path Parameters:**
- `id` (string, required) - Reel UUID

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "author": { ... },
    "caption": "My awesome reel!",
    "video_url": "http://localhost:8000/media/reels/2026/05/10/video1.mp4",
    "privacy": "public",
    "view_count": 150,
    "is_edited": false,
    "created_at": "2026-05-10T10:30:00Z",
    "updated_at": "2026-05-10T10:30:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found` - Reel not found or not owned by user
- `401 Unauthorized` - Missing or invalid token

---

### 4. Update a Reel
**Endpoint:** `PATCH /reels/{id}/`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Description:** Update reel caption or privacy settings. All fields are optional.

**Path Parameters:**
- `id` (string, required) - Reel UUID

**Request Body:**
```
caption (string, optional) - Updated reel caption
privacy (string, optional) - "public" or "only_me"
```

**cURL Example:**
```bash
curl -X PATCH http://localhost:8000/api/reels/550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <access_token>" \
  -F "caption=Updated reel caption!" \
  -F "privacy=only_me"
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Reel updated successfully.",
  "data": { ... }
}
```

**Error Responses:**
- `400 Bad Request` - Invalid input
- `404 Not Found` - Reel not found
- `401 Unauthorized` - Missing or invalid token

---

### 5. Delete a Reel
**Endpoint:** `DELETE /reels/{id}/`

**Authentication:** Required

**Description:** Delete a reel and its video file.

**Path Parameters:**
- `id` (string, required) - Reel UUID

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Reel deleted successfully."
}
```

**Error Responses:**
- `404 Not Found` - Reel not found
- `401 Unauthorized` - Missing or invalid token

---

### 6. Record Reel View
**Endpoint:** `POST /reels/{id}/view/`

**Authentication:** Required

**Description:** Increment the view count for a public reel. Called when a user watches a reel. Uses atomic SQL UPDATE to prevent race conditions.

**Path Parameters:**
- `id` (string, required) - Reel UUID

**Response (200 OK):**
```json
{
  "success": true,
  "message": "View recorded."
}
```

**Error Responses:**
- `404 Not Found` - Reel not found or not public
- `401 Unauthorized` - Missing or invalid token

---

## News Feed API

### 1. Post News Feed
**Endpoint:** `GET /feed/posts/`

**Authentication:** Required

**Description:** Public post feed, newest first. Returns the next batch of unseen posts per user.

**Query Parameters:**
- `page_size` (optional, default: 10, max: 50)
- `search` (optional) - Search by caption; bypasses seen tracking

**Response (200 OK):** Same post shape as the Posts API list, plus `like_count`, `comment_count`, `user_reaction`, `top_reacts`, `is_saved`.

---

### 2. Post News Feed Detail
**Endpoint:** `GET /feed/posts/{id}/`

**Authentication:** Required

**Description:** Single post from the news feed. Use this to open a post from a notification (`post_id`).

**Path Parameters:**
- `id` (uuid, required) - Post UUID

**Response (200 OK):** Same shape as one item from `GET /feed/posts/`.

**Error Responses:**
- `404 Not Found` - Post not found or not visible to you

---

### 3. Reel News Feed
**Endpoint:** `GET /feed/reels/`

**Authentication:** Required

**Description:** Unified reel feed — direct reels and post videos, newest first.

**Query Parameters:**
- `page_size` (optional, default: 10, max: 50)

---

### 4. Community Post Feed
**Endpoint:** `GET /feed/community/{community_id}/`

**Authentication:** Required (must be a community member)

**Query Parameters:**
- `page_size` (optional, default: 10, max: 50)
- `cursor` (optional) - Pagination cursor
- `search` (optional) - Search by caption

---

## News Feed WebSocket

Real-time notifications when new posts or reels are available. The server sends a refresh hint — the client should refresh the relevant REST feed endpoint above.

### Connection
```
ws://localhost:8000/ws/feed/?token=<access_token>
```

**Authentication:** JWT token in query string (same token as REST API).

### Client → Server

Subscribe when entering a feed screen:

```json
{ "type": "subscribe", "feed": "posts" }
```

```json
{ "type": "subscribe", "feed": "reels" }
```

```json
{ "type": "subscribe", "feed": "community", "community_id": "550e8400-e29b-41d4-a716-446655440000" }
```

Unsubscribe when leaving a screen:

```json
{ "type": "unsubscribe", "feed": "posts" }
```

```json
{ "type": "unsubscribe", "feed": "reels" }
```

```json
{ "type": "unsubscribe", "feed": "community", "community_id": "550e8400-e29b-41d4-a716-446655440000" }
```

| Field | Values |
|-------|--------|
| `feed` | `posts`, `reels`, `community` |
| `community_id` | Required for `community` feed |

Community subscribe is rejected silently if the user is not a member.

### Server → Client

Sent when new public content is created (author is excluded):

```json
{
  "type": "feed_update",
  "feed": "posts",
  "community_id": null,
  "message": "New post, please refresh."
}
```

```json
{
  "type": "feed_update",
  "feed": "reels",
  "community_id": null,
  "message": "New reel, please refresh."
}
```

```json
{
  "type": "feed_update",
  "feed": "community",
  "community_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "New post, please refresh."
}
```

**Frontend handling:**
- Show the `message` as a refresh banner
- On refresh, call the matching REST endpoint (`/feed/posts/`, `/feed/reels/`, or `/feed/community/{id}/`)
- For `feed: "posts"` with a `community_id`, show the banner only if the user is a member of that community

**Triggers:**
| Event | Notifies |
|-------|----------|
| Public post created | `posts` (+ `community` if in a community) |
| Public post with video | `posts` + `reels` |
| Public reel created | `reels` |

---

## Notifications

Real-time notifications for reactions and future events. Two separate concepts:

| Concept | Field / API | Meaning |
|---------|-------------|---------|
| **Badge (unread count)** | `unread_count`, `read-all` | User has not opened the notification list since these arrived |
| **Individual read** | `is_read`, `/{id}/read/` | User opened a specific notification |

Device registration for FCM is shared by chat push and future notification push — see [Push Notifications (Firebase)](#push-notifications-firebase).

---

### 1. List Notifications
**Endpoint:** `GET /notifications/`

**Authentication:** Required

**Query Parameters:**
- `page` (optional, default: 1)
- `page_size` (optional, default: 20, max: 50)

**Response (200 OK):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "event": "reaction",
      "message": "Riyad and 2 other people reacted to your post.",
      "actor": {
        "id": "...",
        "name": "Riyad",
        "avatar_url": "..."
      },
      "reaction": "love",
      "others_count": 2,
      "target_type": "post",
      "target_id": "...",
      "post_id": "...",
      "reel_id": null,
      "is_read": false,
      "created_at": "2026-06-30T10:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 1,
    "total_pages": 1,
    "unread_count": 1
  }
}
```

---

### 2. Unread Count
**Endpoint:** `GET /notifications/unread-count/`

**Authentication:** Required

**Description:** Badge count — notifications received after the user last called `read-all` (opened the list).

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "unread_count": 3
  }
}
```

---

### 3. Mark All as Seen (clear badge)
**Endpoint:** `POST /notifications/read-all/`

**Authentication:** Required

**Description:** Clears the badge only — user opened the notification list. Does **not** set `is_read` on individual items. Each notification stays `is_read: false` until opened via `/{id}/read/`.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Notifications marked as seen.",
  "data": {
    "unread_count": 0
  }
}
```

Also pushes a WebSocket `unread_count` event (see below).

---

### 4. Mark One as Read
**Endpoint:** `POST /notifications/{id}/read/`

**Authentication:** Required

**Description:** Marks a single notification as read when the user opens it (e.g. navigates to the post). Does not affect badge unless new notifications arrive after `read-all`.

**Path Parameters:**
- `id` (uuid, required) - Notification UUID

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Notification marked as read.",
  "data": {
    "id": "...",
    "is_read": true,
    "unread_count": 0
  }
}
```

**Error Responses:**
- `404 Not Found` - Notification not found

---

### 5. Delete Notification
**Endpoint:** `DELETE /notifications/{id}/`

**Authentication:** Required

**Description:** Permanently removes a notification from the user's list.

**Path Parameters:**
- `id` (uuid, required) - Notification UUID

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Notification deleted.",
  "data": {
    "unread_count": 0
  }
}
```

**Error Responses:**
- `404 Not Found` - Notification not found

**Frontend flow:**
- On app load: `GET /notifications/unread-count/`
- On WebSocket `new` event: set badge from `data.unread_count`
- On notification list open: `POST /notifications/read-all/` → badge `0`
- On single notification tap: `POST /notifications/{id}/read/` → `is_read: true` for that item
- New notification after `read-all`: badge starts at `1` again

---

### Notifications WebSocket

**Connection:**
```
ws://localhost:8000/ws/notifications/?token=<access_token>
```

Auto-subscribes on connect — no client message needed.

All messages use the same envelope (designed for future Firebase mirroring):

```json
{
  "type": "notification_event",
  "event": "<event_name>",
  "data": { }
}
```

| `event` | When | Action |
|---------|------|--------|
| `new` | New notification created | Show alert / increment badge |
| `unread_count` | After `read-all` (or future sync) | Set badge to `data.unread_count` |

**Event: `new`**
```json
{
  "type": "notification_event",
  "event": "new",
  "data": {
    "id": "...",
    "event": "reaction",
    "message": "Riyad reacted to your post.",
    "actor": {
      "id": "...",
      "name": "Riyad",
      "avatar_url": "..."
    },
    "reaction": "love",
    "others_count": 0,
    "target_type": "post",
    "target_id": "...",
    "post_id": "...",
    "reel_id": null,
    "is_read": false,
    "created_at": "2026-06-30T10:30:00Z",
    "unread_count": 1
  }
}
```

**Event: `unread_count`**
```json
{
  "type": "notification_event",
  "event": "unread_count",
  "data": {
    "unread_count": 0
  }
}
```

| Field | Description |
|-------|-------------|
| `reaction` | The actor's reaction only (`love`, `sad`, `haha`, etc.) |
| `others_count` | Other reactors besides the actor |
| `is_read` | Individual open state — use `POST /notifications/{id}/read/` to set `true` |
| `unread_count` | Badge count in `new` events; full sync in `unread_count` events |
| `post_id` | Open via `GET /feed/posts/{post_id}/` |
| `reel_id` | Set for reel reactions (reel detail API coming later) |
| `target_type` | `post`, `media`, or `reel` |

**Triggered when:** Someone reacts to your public post, media item, or reel (not on reaction remove; not when you react to your own content).

---

## Push Notifications (Firebase)

Used for alerts when the app is in the **background or closed**. In-app real-time still uses WebSocket.

| Channel | When |
|---------|------|
| WebSocket | App open — chat, feed, notifications |
| FCM push | App background/closed — system tray notification |

**Requirements (Flutter / mobile):**
- Firebase project with Android + iOS apps configured
- Real `fcm_token` from `FirebaseMessaging.instance.getToken()` (Postman fake tokens will not deliver to a phone)
- Register token after central ERP login
- iOS: APNs key uploaded to Firebase; test on a **physical device**

---

### 1. Register Device
**Endpoint:** `POST /devices/register/`

**Authentication:** Required (`Authorization: Bearer <token>`)

**Description:** Stores the device FCM token for push. Call after login and whenever the FCM token refreshes.

**Body:**
```json
{
  "device_id": "stable-device-uuid-from-app",
  "fcm_token": "firebase-messaging-token",
  "platform": "android"
}
```

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | Stable ID per device (from Flutter) |
| `fcm_token` | Yes | From Firebase Messaging SDK |
| `platform` | Yes | `android`, `ios` |

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Device registered."
}
```

If the same `device_id` is sent again, the token is updated (`"Device updated."`).

**Error Responses:**
- `400` — missing `device_id` / `fcm_token`, or invalid `platform`
- `401` — missing or invalid Bearer token

---

### 2. Unregister Device
**Endpoint:** `DELETE /devices/unregister/`

**Authentication:** Required

**Description:** Removes the device token on logout.

**Body:**
```json
{
  "device_id": "stable-device-uuid-from-app"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Device unregistered."
}
```

---

## Chat API

Direct messages (DM) and group chats. Text is sent over WebSocket; media/docs over HTTP then WebSocket broadcast.

---

### 1. List Conversations
**Endpoint:** `GET /conversations/`

**Authentication:** Required

**Description:** All conversations for the authenticated user, sorted by `last_activity`.

---

### 2. Start DM
**Endpoint:** `POST /conversations/`

**Authentication:** Required

**Body:**
```json
{
  "user_id": "target-user-uuid"
}
```

---

### 3. Search Users (start chat)
**Endpoint:** `GET /conversations/user/search/?q=<name>`

**Authentication:** Required

**Query Parameters:**
- `q` (required, min 2 characters) — search by name

---

### 4. List Participants
**Endpoint:** `GET /conversations/{conv_id}/participants/`

**Authentication:** Required

---

### 5. Message History
**Endpoint:** `GET /conversations/{conv_id}/messages/`

**Authentication:** Required (must be a participant)

**Query Parameters:**
- `page_size` (optional, default: 20, max: 50)
- `cursor` (optional) — load older messages

**Description:** Newest first. Opening the first page marks messages as read (DM).

---

### 6. Upload Media / Documents
**Endpoint:** `POST /conversations/{conv_id}/messages/`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Fields:**
- `files` — one or more files
- `body` (optional) — caption
- `reply_to_id` (optional) — UUID

**Response (201):** Message object. Then notify other clients via WebSocket (see below).

---

### Chat WebSocket

**Connection:**
```
ws://localhost:8000/ws/chat/{conv_id}/?token=<access_token>
```

**Authentication:** JWT in query string (same as REST).

User must be a **participant** of `conv_id`; otherwise the connection is rejected.

#### Client → Server

**Send text message:**
```json
{
  "type": "message",
  "body": "Hello!",
  "reply_to_id": null
}
```

**After media HTTP upload — broadcast to room:**
```json
{
  "type": "media_sent",
  "message_id": "uuid-from-201-response"
}
```

**Typing:**
```json
{ "type": "typing", "is_typing": true }
```

**Mark read:**
```json
{ "type": "read", "message_id": "uuid" }
```

#### Server → Client

**New message:**
```json
{
  "type": "message",
  "data": {
    "id": "...",
    "sender": {
      "id": "...",
      "name": "...",
      "avatar_url": "..."
    },
    "type": "text",
    "body": "Hello!",
    "reply_to": null,
    "media": [],
    "reactions": {},
    "read_by_count": 0,
    "is_edited": false,
    "is_deleted": false,
    "created_at": "...",
    "updated_at": "..."
  }
}
```

Other events: `typing`, `presence`, `message_edited`, `message_deleted`, `react`, call/WebRTC signaling.

---

### Chat Push Notification (FCM)

Sent automatically when a **new message** is created (text via WebSocket, media after `media_sent`).

**Recipients:** All conversation participants **except the sender**.

**System notification (tray):**

| Chat type | Title | Body |
|-----------|-------|------|
| DM | Sender name | Message text (or preview) |
| Group | Group / community name | `{sender}: {message}` |
| Media (no text) | Sender name | `Sent a photo` / `Sent a document` |

**FCM `data` payload (for Flutter routing):**
```json
{
  "type": "chat_message",
  "conv_id": "conversation-uuid",
  "message_id": "message-uuid",
  "payload": "{...stringified WebSocket message data...}"
}
```

**Flutter handling:**
1. On login → `POST /devices/register/` with real `fcm_token`
2. On logout → `DELETE /devices/unregister/`
3. On notification tap → parse `conv_id` from `data` → open chat screen
4. Optionally load history: `GET /conversations/{conv_id}/messages/`
5. Suppress duplicate banner if user is already on that chat screen (client-side)

**Testing notes:**
- Postman **cannot** receive FCM on a phone — use a Flutter build with a real Firebase token
- Register token for the **recipient** user, not the sender
- Put recipient app in **background** to see the system notification
- Server log `FCM sent | success=1 failure=0` means Firebase accepted the push
- Invalid tokens are removed automatically after failed send; re-register from the app

---

### Chat + Push Flow

```text
Text:
  Client → WS {"type":"message","body":"..."}
  Server → saves DB → WS broadcast to room → FCM to other participants

Media:
  Client → POST /conversations/{id}/messages/ (multipart)
  Client → WS {"type":"media_sent","message_id":"..."}
  Server → WS broadcast → FCM to other participants
```

---

## Common Response Format

All endpoints follow a consistent response format:

**Success Response:**
```json
{
  "success": true,
  "message": "Optional message",
  "data": { /* endpoint-specific data */ },
  "meta": { /* optional pagination or metadata */ }
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Error description",
  "errors": {
    "field_name": ["Error message for field"]
  }
}
```

---

## Privacy Settings

Both Posts and Reels support two privacy levels:

| Value | Description |
|-------|-------------|
| `public` | Visible to all users (default) |
| `only_me` | Only visible to the owner |

---

## Pagination

Cursor-based pagination is used for listing endpoints. Each page response includes:

- `next_cursor` - Cursor for the next page (null if no more items)
- `has_more` - Boolean indicating if there are more items
- `page_size` - Number of items returned

**Example: Get next page**
```bash
curl "http://localhost:8000/api/posts/?cursor=<next_cursor>" \
  -H "Authorization: Bearer <access_token>"
```

---

## Error Codes

| Status | Description |
|--------|-------------|
| `200` | Success (GET, PATCH, DELETE) |
| `201` | Created (POST) |
| `400` | Bad request (validation error) |
| `401` | Unauthorized (missing/invalid token) |
| `404` | Not found (resource doesn't exist) |
| `500` | Server error |

---

## Rate Limiting

No explicit rate limiting is currently implemented. Clients should implement reasonable request throttling.

---

## File Upload Limits

- Maximum file size: Check Django settings (typically 100MB)
- Supported image formats: JPEG, PNG, GIF, WebP
- Supported video formats: MP4, MOV, AVI, WebM

---

## Notes

1. **Cursor Pagination**: Cursors are base64-encoded strings combining `created_at` and object `id`. They should be treated as opaque strings and passed directly without modification.

2. **Media Ordering**: When updating post media, `add_captions` and `edit_media_caption` are positionally matched with their respective file/ID lists.

3. **Atomicity**: View counting uses Django's `F()` expression for atomic updates, ensuring accuracy under high concurrency.

4. **Ownership**: All detail/update/delete operations require the authenticated user to be the resource owner.
