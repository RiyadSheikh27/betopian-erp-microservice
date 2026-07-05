# Contents API Documentation

## Base URL
```
http://localhost:8000/api/v1/
```

## Authentication
All protected endpoints require our own JWT (issued by `POST /login/`). Include it in the request header:
```
Authorization: Bearer <access_token>
```

### Token model
The app uses **two different tokens** — do not confuse them:

| Token | Issued by | Sent by client | Used for |
| --- | --- | --- | --- |
| **App JWT** (`access_token` / `refresh_token`) | This service, on `POST /login/` | On every request (`Authorization: Bearer …`) and WebSocket (`?token=…`) | Authenticating the caller to this API |
| **Microsoft (central) access token** | Microsoft Entra ID | Only once, in the `POST /login/` body | Stored server-side as `central_access_token`; used **internally** for calls to the central ERP (e.g. employee-directory search) |

The Microsoft access token is captured at login and stored on the user record. Clients **never** send it again — the server attaches it automatically for central ERP calls.

> **Note:** Microsoft access tokens are short-lived (~60–80 min). Once the stored `central_access_token` expires, central ERP calls (such as user search) return no results until the user logs in again with a fresh Microsoft token.

### Response envelope
All endpoints return a consistent envelope:
```json
{
  "success": true,
  "message": "Request successful",
  "data": {},
  "errors": null,
  "meta": { "timestamp": "2026-07-02T09:19:04.840964Z" }
}
```

---

## Authentication API

### 1. SSO Login
**Endpoint:** `POST /login/`

**Authentication:** None (public)

**Description:** Verifies a Microsoft Entra ID token against the central ERP, mirrors the user locally, stores the Microsoft token as `central_access_token`, and issues this service's own JWT pair.

**Body:** (send either `access_token` or `id_token`)
```json
{
  "access_token": "<microsoft_access_token>",
  "id_token": "<microsoft_id_token>",
  "appVersion": "1.0.0",
  "deviceId": "stable-device-uuid-from-app",
  "fcm_token": "firebase-messaging-token",
  "platform": "android"
}
```

| Field | Required | Description |
| --- | --- | --- |
| `access_token` | Conditional | Microsoft access token. Required if `id_token` is not provided. |
| `id_token` | Conditional | Microsoft ID token. Required if `access_token` is not provided. |
| `appVersion` | Optional | Client app version (logged only). |
| `deviceId` | Optional* | Stable device ID. Required when registering for push. |
| `fcm_token` | Optional* | Firebase Messaging token. Register device for push when provided. |
| `platform` | Optional* | `android` or `ios`. Required when `fcm_token` is provided. |

\* For push notifications, send all three together: `deviceId`, `fcm_token`, and `platform`. Login works without them (no push until they are sent on a later login).

**Response (200 OK):**
```json
{
  "success": true,
  "message": "SSO login successful.",
  "data": {
    "access_token": "<app_jwt_access_token>",
    "refresh_token": "<app_jwt_refresh_token>",
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "central_id": 10007558,
      "employee_id": "11016",
      "name": "Md. Riyad Hossain",
      "email": "riyad.hossain@betopiagroup.com",
      "username": "riyad.hossain",
      "phone": "+8801836851918",
      "department": "Admin & Legal Management",
      "position": "Sr. Executive, SCM",
      "location": "",
      "company": "Betopia Group",
      "avatar_url": "https://erp.betopiagroup.com/web/image/hr.employee/10007558/image_256?access_token=..."
    }
  },
  "errors": null,
  "meta": { "timestamp": "2026-07-02T09:19:04.840964Z" }
}
```

**Error responses:**

| Status | When |
| --- | --- |
| `422` | Payload invalid (neither `access_token` nor `id_token` supplied). |
| `401` | Microsoft token invalid or expired. |
| `502` / `503` | Central ERP profile service unreachable **and** no stored user to fall back to. |

> If the central profile service is temporarily unavailable but the user already exists locally, login succeeds using the stored profile data (the `central_access_token` is **not** refreshed in this case).

---

### 2. Logout
**Endpoint:** `POST /logout/`

**Authentication:** Required

**Description:** Logs the logout event. This service does not maintain server-side sessions, so no token is invalidated server-side — the client should discard its stored JWTs.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Logged out successfully.",
  "data": null,
  "errors": null,
  "meta": { "timestamp": "2026-07-02T09:19:04.840964Z" }
}
```

---

### 3. Get Profile
**Endpoint:** `GET /profile/`

**Authentication:** Required

**Description:** Returns the authenticated user's profile (read-only mirror of central ERP data).

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "central_id": 10007558,
    "employee_id": "11016",
    "name": "Md. Riyad Hossain",
    "email": "riyad.hossain@betopiagroup.com",
    "username": "riyad.hossain",
    "phone": "+8801836851918",
    "department": "Admin & Legal Management",
    "position": "Sr. Executive, SCM",
    "location": "",
    "company": "Betopia Group",
    "avatar_url": "https://erp.betopiagroup.com/web/image/hr.employee/10007558/image_256?access_token=..."
  },
  "errors": null,
  "meta": { "timestamp": "2026-07-02T09:19:04.840964Z" }
}
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

Social activity alerts (reactions, comments). Each notification is stored in the DB, delivered over **WebSocket** when the app is open, and sent via **FCM push** when the app is in the background or closed.

### Overview

| Concept | Field / API | Meaning |
|---------|-------------|---------|
| **Badge (unread count)** | `unread_count`, `read-all` | Notifications received since the user last opened the notification list |
| **Individual read** | `is_read`, `/{id}/read/` | User opened a specific notification (e.g. navigated to the post) |

| Channel | Endpoint | When |
|---------|----------|------|
| **REST** | `GET /notifications/` | Load history, badge on app open |
| **WebSocket** | `ws://host/ws/notifications/?token=` | Real-time while app is open |
| **FCM push** | Automatic (no client trigger) | App background / closed — requires device registration |

Device registration: at **login** or **`POST /devices/register/`** — see [Push Notifications (Firebase)](#push-notifications-firebase).

---

### Notification event types

| `data.event` | Trigger | Recipient |
|--------------|---------|-----------|
| `reaction` | Someone reacts to your public post, media, or reel | Content owner |
| `comment` | Someone comments on your post/reel/media | Content owner |
| `comment` (reply) | Someone replies to your comment | Parent comment author |

**Not notified:** self-actions, reaction removed, commenting on your own content, replying to yourself.

#### Reaction payload fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Notification ID — use for read/delete |
| `event` | string | `"reaction"` |
| `message` | string | Human-readable text, e.g. `"Riyad and 2 others reacted to your post."` |
| `actor` | object | `{ id, name, avatar_url }` — who triggered it |
| `reaction` | string | Actor's reaction: `love`, `angry`, `haha`, `wow`, `sad`, `care` |
| `others_count` | int | Other reactors besides the actor |
| `target_type` | string | `post`, `media`, or `reel` |
| `target_id` | uuid | ID of the reacted item |
| `post_id` | uuid \| null | Post to open (set for `post` and `media` targets) |
| `reel_id` | uuid \| null | Reel to open (set for `reel` targets) |
| `is_read` | bool | `false` until `POST /notifications/{id}/read/` |
| `created_at` | ISO datetime | When the notification was created |
| `unread_count` | int | Current badge count (WebSocket / push only) |

#### Comment payload fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Notification ID |
| `event` | string | `"comment"` |
| `message` | string | e.g. `"Riyad commented on your post."` or `"Riyad replied to your comment."` |
| `actor` | object | `{ id, name, avatar_url }` |
| `comment_id` | uuid | The new comment |
| `comment_body` | string | Comment preview (max 120 chars) |
| `parent_id` | uuid \| null | Set when this is a reply |
| `target_type` | string | `post`, `media`, or `reel` |
| `target_id` | uuid | ID of the commented item |
| `post_id` | uuid \| null | Post to open |
| `reel_id` | uuid \| null | Reel to open |
| `is_read` | bool | Individual read state |
| `created_at` | ISO datetime | Creation time |
| `unread_count` | int | Current badge count (WebSocket / push only) |

---

### 1. List Notifications
**Endpoint:** `GET /notifications/`

**Authentication:** Required

**Query Parameters:**
| Param | Default | Max | Description |
|-------|---------|-----|-------------|
| `page` | 1 | — | Page number |
| `page_size` | 20 | 50 | Items per page |

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
    },
    {
      "id": "...",
      "event": "comment",
      "message": "Sarah replied to your comment.",
      "actor": { "id": "...", "name": "Sarah", "avatar_url": "..." },
      "comment_id": "...",
      "comment_body": "Thanks!",
      "parent_id": "...",
      "target_type": "post",
      "target_id": "...",
      "post_id": "...",
      "reel_id": null,
      "is_read": false,
      "created_at": "2026-07-04T10:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 2,
    "total_pages": 1,
    "unread_count": 2
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
- `404 Not Found` — Notification not found

---

### 6. Register Device (push)
**Endpoint:** `POST /devices/register/`

**Authentication:** Required

**Description:** Register or replace the user's FCM token for push notifications. Also supported at login — see [Push Notifications (Firebase)](#push-notifications-firebase). Each user keeps **one** token row (re-register replaces the previous token).

**Body:** (`device_id` or `deviceId` accepted)
```json
{
  "deviceId": "stable-device-uuid-from-app",
  "fcm_token": "firebase-messaging-token",
  "platform": "android"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Device registered."
}
```

---

### 7. Unregister Device
**Endpoint:** `DELETE /devices/unregister/`

**Authentication:** Required

**Description:** Remove device token on logout.

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

### Frontend integration flow

```
App launch
  → GET /notifications/unread-count/          (badge)
  → Connect ws://host/ws/notifications/?token=<access_token>

On WebSocket event "new"
  → Update badge from data.unread_count
  → Show in-app alert / prepend to list

On notification list open
  → GET /notifications/
  → POST /notifications/read-all/           (badge → 0)

On notification tap
  → POST /notifications/{id}/read/
  → Navigate using post_id / reel_id / comment_id

On login (or FCM token refresh)
  → POST /login/ with push fields, OR POST /devices/register/

On logout
  → DELETE /devices/unregister/
```

**Navigation by event:**

| `data.event` | Open |
|--------------|------|
| `reaction` on post/media | `GET /feed/posts/{post_id}/` |
| `reaction` on reel | Reel detail (use `reel_id`) |
| `comment` | Same as above + scroll to `comment_id` if supported |

---

### Notifications WebSocket

**Connection:**
```
ws://localhost:8000/ws/notifications/?token=<access_token>
```

**Authentication:** App JWT in query string (same token as REST `Authorization: Bearer`).

Auto-subscribes on connect — no client message required. User joins group `notify_{user_id}`.

**Envelope (all server → client messages):**
```json
{
  "type": "notification_event",
  "event": "<event_name>",
  "data": { }
}
```

| `event` | When | Client action |
|---------|------|---------------|
| `new` | Reaction or comment notification created | Show alert, update badge, refresh list |
| `unread_count` | After `POST /notifications/read-all/` | Set badge to `data.unread_count` |

**Event: `new` (reaction)**
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

**Event: `new` (comment)**
```json
{
  "type": "notification_event",
  "event": "new",
  "data": {
    "id": "...",
    "event": "comment",
    "message": "Riyad commented on your post.",
    "actor": { "id": "...", "name": "Riyad", "avatar_url": "..." },
    "comment_id": "...",
    "comment_body": "Nice post!",
    "parent_id": null,
    "target_type": "post",
    "target_id": "...",
    "post_id": "...",
    "reel_id": null,
    "is_read": false,
    "created_at": "2026-07-04T10:30:00Z",
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

> FCM push uses the same `data` object as WebSocket — see [Social push (FCM)](#social-push-fcm) below.

---

## Push Notifications (Firebase)

Used when the app is in the **background or closed**. In-app real-time uses WebSocket (see [Notifications WebSocket](#notifications-websocket) and [Chat WebSocket](#chat-websocket)).

| Channel | When |
|---------|------|
| WebSocket | App open — notifications, chat, feed |
| FCM push | App background/closed — system tray |

**Requirements (Flutter / mobile):**
- Firebase project with Android + iOS apps configured
- Real `fcm_token` from `FirebaseMessaging.instance.getToken()`
- Register via **login** or **`POST /devices/register/`** (see [Register Device](#6-register-device-push))
- Re-register when Firebase refreshes the token (`onTokenRefresh`)
- iOS: APNs key uploaded to Firebase; test on a **physical device**

**Storage:** One FCM token per user — each register call **replaces** the previous token.

---

### Register at login

**Endpoint:** `POST /login/`

Include push fields in the login body:

```json
{
  "access_token": "<microsoft_access_token>",
  "deviceId": "stable-device-uuid-from-app",
  "fcm_token": "firebase-messaging-token",
  "platform": "android"
}
```

| Field | Required for push | Values |
|-------|-------------------|--------|
| `deviceId` | Yes | Stable ID per device |
| `fcm_token` | Yes | From Firebase Messaging SDK |
| `platform` | Yes | `android`, `ios` |

All three must be sent together. Login works without them (no push until registered later).

---

### Social push (FCM)

Sent automatically when a reaction or comment notification is created. No client API to trigger push.

**System notification (tray):**

| Type | Title | Body |
|------|-------|------|
| Reaction / comment | Actor name | `message` from payload |

**FCM `data` payload:**
```json
{
  "type": "notification_event",
  "event": "new",
  "notification_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": "{\"id\":\"...\",\"event\":\"reaction\",\"message\":\"Riyad reacted to your post.\",...}"
}
```

| Field | Description |
|-------|-------------|
| `type` | Always `"notification_event"` for social alerts |
| `event` | Always `"new"` for new notifications |
| `notification_id` | Same as `id` in WebSocket / REST |
| `payload` | **Stringified JSON** — same object as WebSocket `data` |

**Flutter handling:**
```dart
// Background / terminated — user taps notification
FirebaseMessaging.onMessageOpenedApp.listen((message) {
  if (message.data['type'] == 'notification_event') {
    final data = jsonDecode(message.data['payload']);
    if (data['post_id'] != null) openPost(data['post_id']);
    else if (data['reel_id'] != null) openReel(data['reel_id']);
  }
});

// Foreground — suppress if ws/notifications already handled it
FirebaseMessaging.onMessage.listen((message) {
  if (message.data['type'] == 'notification_event') {
    showLocalBanner(message); // optional
  }
});
```

---

### Chat push (FCM)

See [Chat Push Notification (FCM)](#chat-push-notification-fcm) in the Chat API section.

| `data.type` | Trigger |
|-------------|---------|
| `notification_event` | Reaction, comment |
| `chat_message` | New chat message |
| `incoming_call` | Incoming 1:1 voice/video call |

> **Full Postman reference:** [`CHAT_AND_CALLING.md`](CHAT_AND_CALLING.md) — every chat/call HTTP endpoint and WebSocket message with bodies and responses, plus step-by-step test flows.

---

## Chat & Calling

Direct messages (DM), group chats, and **1:1 voice/video calls** (WhatsApp-style).

**Postman-ready reference (every HTTP + WS body/response):** [`CHAT_AND_CALLING.md`](CHAT_AND_CALLING.md)

The sections below are a summary; use the linked doc for full request/response examples and Postman test flows.

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

Other events: `typing`, `presence`, `message_edited`, `message_deleted`, `react`.

> **Calls are not signaled on this socket.** Use the [Calls API](#calls-api-11-webrtc) and `/ws/calls/{call_id}/` instead.

---

## Calls API (1:1 WebRTC)

WhatsApp-style 1:1 audio/video. **REST** manages ring/accept/decline/end; **WebSocket** relays WebRTC only; **FCM** wakes callee when app is closed.

See [`CHAT_AND_CALLING.md`](CHAT_AND_CALLING.md) for the full tutorial.

### 1. Get TURN credentials

**Endpoint:** `GET /turn-credentials/`

**Authentication:** Required

**Description:** Short-lived STUN/TURN ICE servers for WebRTC. Fetch before creating `RTCPeerConnection`.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "ice_servers": [
      { "urls": ["stun:103.149.105.4:3478"] },
      {
        "urls": [
          "turn:103.149.105.4:3478?transport=udp",
          "turn:103.149.105.4:3478?transport=tcp"
        ],
        "username": "1735689600:user-uuid",
        "credential": "base64-hmac..."
      }
    ]
  }
}
```

---

### 2. Initiate call

**Endpoint:** `POST /calls/initiate/`

**Authentication:** Required

**Description:** Start a 1:1 call from **any screen** (profile, chat list, etc.). Creates DM conversation if needed. Sends high-priority FCM + notifications WebSocket to callee.

**Body:**
```json
{
  "callee_id": "target-user-uuid",
  "call_type": "video"
}
```

| Field | Required | Values |
| --- | --- | --- |
| `callee_id` | Yes | User UUID to call |
| `call_type` | No | `audio` (default) or `video` |

**Response (201):**
```json
{
  "success": true,
  "message": "Call ringing.",
  "data": {
    "call": {
      "id": "call-session-uuid",
      "conv_id": "conversation-uuid",
      "caller_id": "...",
      "callee_id": "...",
      "call_type": "video",
      "status": "ringing",
      "duration": 0,
      "created_at": "...",
      "ended_at": null
    },
    "caller": { "id": "...", "name": "...", "avatar_url": "..." },
    "callee": { "id": "...", "name": "...", "avatar_url": "..." }
  }
}
```

**Errors:**
- `409` — caller or callee already in an active call
- `400` — cannot call yourself

**Frontend next steps:** Connect `ws://host/ws/calls/{call.id}/?token=...`, show "Calling…", fetch TURN creds.

---

### 3. Get call status

**Endpoint:** `GET /calls/{call_id}/`

**Authentication:** Required (caller or callee only)

---

### 4. Accept call

**Endpoint:** `POST /calls/{call_id}/accept/`

**Authentication:** Required (**callee only**)

**Description:** Callee accepts. Broadcasts `call_accepted` on call WS + notifications WS.

---

### 5. Decline call

**Endpoint:** `POST /calls/{call_id}/decline/`

**Authentication:** Required (**callee only**, while `status` is `ringing`)

**Description:** Creates one call log message in chat (`declined`).

---

### 6. Cancel / miss (caller)

**Endpoint:** `POST /calls/{call_id}/cancel/`

**Authentication:** Required (**caller only**, while `status` is `ringing`)

**Description:** Caller hung up before answer. Logged as `missed` for callee.

---

### 7. Report media connected (optional)

**Endpoint:** `POST /calls/{call_id}/connected/`

**Authentication:** Required

**Description:** Client reports WebRTC media connected (`status` → `connected`). Optional — use for analytics or server-side UI sync.

---

### 8. End call

**Endpoint:** `POST /calls/{call_id}/end/`

**Authentication:** Required (caller or callee)

**Description:** **Single** end point — creates **one** call log in chat. Idempotent if already ended.

**Body:**
```json
{
  "duration": 125
}
```

`duration` — call length in seconds (for completed calls).

---

### Call WebSocket (WebRTC signaling)

**Connection:**
```
ws://localhost:8000/ws/calls/{call_id}/?token=<access_token>
```

Only caller/callee may connect. Rejected if call is not active (`ringing`, `accepted`, or `connected`).

**Client → Server:**

```json
{ "type": "offer", "sdp": { "type": "offer", "sdp": "..." } }
{ "type": "answer", "sdp": { "type": "answer", "sdp": "..." } }
{ "type": "ice_candidate", "candidate": { "candidate": "...", "sdpMid": "0", "sdpMLineIndex": 0 } }
{ "type": "ping" }
```

**Server → Client:** Same types (relayed from peer with `sender_id`), plus:

```json
{ "type": "call_accepted", "call": { ... }, "accepted_by": "user-uuid" }
{ "type": "call_connected", "call": { ... } }
{ "type": "call_ended", "call": { ... } }
{ "type": "pong" }
```

**Do not** end calls via WebSocket — use `POST /calls/{id}/end/`.

---

### Incoming call push (FCM)

High-priority push when `POST /calls/initiate/` runs. Callee receives even if app is backgrounded.

**FCM `data` payload:**
```json
{
  "type": "incoming_call",
  "call_id": "call-session-uuid",
  "conv_id": "conversation-uuid",
  "caller_id": "caller-uuid",
  "caller_name": "Jane Doe",
  "caller_avatar": "https://...",
  "call_type": "video"
}
```

**Also delivered on notifications WebSocket** (`/ws/notifications/`) when app is open:

```json
{
  "type": "incoming_call",
  "call": { "id": "...", "conv_id": "...", "call_type": "video", "status": "ringing" },
  "caller": { "id": "...", "name": "...", "avatar_url": "..." }
}
```

**Flutter handling:**
1. Background FCM → show CallKit / full-screen incoming UI
2. User accepts → `POST /calls/{call_id}/accept/`
3. `GET /turn-credentials/` → create `RTCPeerConnection`
4. Connect call WebSocket → exchange offer/answer/ICE
5. Show "Connecting…" until ICE `connected`; hang up via `POST /calls/{id}/end/`

---

### Call state values

| status | Meaning |
|--------|---------|
| `ringing` | Waiting for callee |
| `accepted` | Callee accepted; WebRTC negotiation |
| `connected` | Client reported media up (optional) |
| `ended` | Completed call |
| `missed` | No answer / caller cancelled |
| `declined` | Callee rejected |
| `cancelled` | Reserved |

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
1. On login → send push fields in `POST /login/`, **or** `POST /devices/register/` after login
2. On logout → `DELETE /devices/unregister/`
3. On notification tap → parse `conv_id` from `data` → open chat screen
4. Optionally load history: `GET /conversations/{conv_id}/messages/`
5. Suppress duplicate banner if user is already on that chat screen (client-side)

**Testing notes:**
- Postman **cannot** receive FCM on a phone — use a Flutter build with a real Firebase token
- Register token for the **recipient** user at login, not the sender
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
