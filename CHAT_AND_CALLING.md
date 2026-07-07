# Chat & Calling — Full Guide + Postman Reference

Tutorial (what/why) plus **every HTTP and WebSocket request** with bodies and responses for Postman testing.

Also summarized in [`api_documentation.md`](api_documentation.md#chat--calling).

---

## Table of contents

**Postman reference**
1. [Setup (auth, base URL, envelope)](#1-setup-auth-base-url-envelope)
2. [Chat — HTTP endpoints](#2-chat--http-endpoints)
3. [Chat — WebSocket](#3-chat--websocket)
4. [Calls — HTTP endpoints](#4-calls--http-endpoints)
5. [Calls — WebSocket](#5-calls--websocket)
6. [Notifications WebSocket (incoming call)](#6-notifications-websocket-incoming-call)
7. [Postman test flows](#7-postman-test-flows)

**Tutorial**
8. [Architecture overview](#8-architecture-overview)
9. [Technologies explained](#9-technologies-explained)
10. [Call state machine](#10-call-state-machine)
11. [FCM push payloads](#11-fcm-push-payloads)
12. [Frontend developer checklist](#12-frontend-developer-checklist)

---

## 1. Setup (auth, base URL, envelope)

### Base URL

| Environment | REST base | WebSocket base |
|-------------|-----------|----------------|
| Local Docker | `http://localhost:8000/api/v1/` | `ws://localhost:8000` |
| Production | `https://social-media.betopiagroup.com/api/v1/` | `wss://social-media.betopiagroup.com` |

### Authentication

All protected REST endpoints:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

Get `access_token` from `POST /api/v1/login/` (see main API docs).

WebSockets pass the same JWT in the query string:

```
?token=<access_token>
```

### Response envelope (every REST endpoint)

**Success:**
```json
{
  "success": true,
  "message": "Request successful",
  "data": { },
  "errors": null,
  "meta": {
    "timestamp": "2026-07-05T10:30:00.123456+06:00"
  }
}
```

**Error:**
```json
{
  "success": false,
  "message": "Conversation not found.",
  "data": null,
  "errors": {
    "field_name": ["Error detail"]
  },
  "meta": {
    "timestamp": "2026-07-05T10:30:00.123456+06:00"
  }
}
```

Pagination endpoints add to `meta`: `next_cursor`, `has_more`, `page_size`.

### Postman tips

- Create an environment variable `base_url` = `http://localhost:8000/api/v1`
- Create `access_token` from login; use `Bearer {{access_token}}` on all requests
- **WebSocket:** Postman → New → WebSocket → URL with `?token={{access_token}}`
- FCM / WebRTC media **cannot** be tested in Postman — use two phones or WS + REST only

---

## 2. Chat — HTTP endpoints

### 2.1 Search users (start chat)

Find employees in central ERP to start a DM, or list all employees with pagination.

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/conversations/user/search/` |
| **Auth** | Required |

**Query parameters**

| Param | Required | Default | Max | Description |
|-------|----------|---------|-----|-------------|
| `q` | No | — | — | Search text; min 2 characters when provided |
| `page` | No | `1` | — | Page number (list mode only, when `q` is omitted) |
| `page_size` | No | `20` | `50` | Items per page (list mode only) |

**Example — list all (paginated)**
```http
GET /api/v1/conversations/user/search/?page=1&page_size=20
Authorization: Bearer eyJ...
```

**Example — search by name**
```http
GET /api/v1/conversations/user/search/?q=john
Authorization: Bearer eyJ...
```

**Response `200` (search mode)**
```json
{
  "success": true,
  "message": "Request successful",
  "data": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "employee_id": "EMP001",
      "name": "John Doe",
      "position": "Software Engineer",
      "avatar_url": "https://erp.example.com/avatar.jpg",
      "is_active_on_social": true
    },
    {
      "id": null,
      "employee_id": "EMP099",
      "name": "John Smith",
      "position": "HR Manager",
      "avatar_url": null,
      "is_active_on_social": false
    }
  ],
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**Response `200` (list mode — no `q`)**
```json
{
  "success": true,
  "message": "Request successful",
  "data": [ "..." ],
  "errors": null,
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 842,
    "total_pages": 43,
    "has_more": true,
    "timestamp": "..."
  }
}
```

| Field | Meaning |
|-------|---------|
| `id` | Local user UUID — `null` if not registered on social yet |
| `is_active_on_social` | `true` if you can DM them (`id` is set) |

**Errors**

| Status | When |
|--------|------|
| `400` | `q` provided but shorter than 2 chars |
| `401` | Missing/invalid token |

---

### 2.2 List conversations

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/conversations/` |
| **Auth** | Required |

**Query parameters**

| Param | Default | Max | Description |
|-------|---------|-----|-------------|
| `page_size` | `20` | `50` | Items per page |
| `cursor` | — | — | From previous `meta.next_cursor` |

**Example request**
```http
GET /api/v1/conversations/?page_size=20
Authorization: Bearer eyJ...
```

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": [
    {
      "id": "conv-uuid-here",
      "type": "dm",
      "other_user": {
        "id": "user-uuid",
        "name": "Jane Doe",
        "avatar_url": "https://...",
        "is_online": true,
        "last_seen": "2026-07-05T09:00:00Z"
      },
      "group_name": null,
      "group_avatar": null,
      "last_message": {
        "id": "msg-uuid",
        "sender_name": "Jane Doe",
        "type": "text",
        "body": "See you tomorrow",
        "created_at": "2026-07-05T09:55:00Z"
      },
      "unread_count": 2,
      "participant_count": 2,
      "last_activity": "2026-07-05T09:55:00Z"
    },
    {
      "id": "group-conv-uuid",
      "type": "group",
      "other_user": null,
      "group_name": "Engineering Team",
      "group_avatar": "https://.../cover.jpg",
      "last_message": { "id": "...", "sender_name": "...", "type": "text", "body": "...", "created_at": "..." },
      "unread_count": 0,
      "participant_count": 15,
      "last_activity": "2026-07-05T08:00:00Z"
    }
  ],
  "errors": null,
  "meta": {
    "next_cursor": "2026-07-04T12:00:00Z|older-conv-uuid",
    "has_more": true,
    "page_size": 20,
    "timestamp": "..."
  }
}
```

**Errors**

| Status | When |
|--------|------|
| `400` | Invalid `cursor` |
| `401` | Unauthorized |

---

### 2.3 Start or get DM

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/conversations/` |
| **Auth** | Required |

**Request body**
```json
{
  "user_id": "target-user-uuid"
}
```

**Response `201`** (new DM created)
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "id": "new-conv-uuid",
    "type": "dm",
    "other_user": {
      "id": "target-user-uuid",
      "name": "Jane Doe",
      "avatar_url": "",
      "is_online": false,
      "last_seen": "2026-07-05T08:00:00Z"
    },
    "group_name": null,
    "group_avatar": null,
    "last_message": null,
    "unread_count": 0,
    "participant_count": 2,
    "last_activity": "2026-07-05T10:00:00Z"
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**Response `200`** — same shape if DM already existed.

**Errors**

| Status | Message |
|--------|---------|
| `400` | `user_id required` / `Cannot message yourself` |
| `404` | `User not found or not yet active on social` |

---

### 2.4 List participants

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/conversations/{conv_id}/participants/` |
| **Auth** | Required (must be participant) |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": [
    {
      "id": "user-uuid-1",
      "name": "Alice",
      "avatar_url": "https://...",
      "is_online": true,
      "last_seen": "2026-07-05T10:00:00Z"
    },
    {
      "id": "user-uuid-2",
      "name": "Bob",
      "avatar_url": "",
      "is_online": false,
      "last_seen": "2026-07-04T18:00:00Z"
    }
  ],
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**Errors:** `404` if not a participant.

---

### 2.5 Message history

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/conversations/{conv_id}/messages/` |
| **Auth** | Required (participant) |

**Query parameters**

| Param | Default | Description |
|-------|---------|-------------|
| `page_size` | `20` | Max `50` |
| `cursor` | — | Load **older** messages (scroll up) |

First page (no cursor) auto-marks DM messages as read.

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": [
    {
      "id": "msg-uuid",
      "sender": {
        "id": "sender-uuid",
        "name": "Jane Doe",
        "avatar_url": "https://..."
      },
      "type": "text",
      "body": "Hello!",
      "reply_to": null,
      "media": [],
      "reactions": { "love": 2, "haha": 1 },
      "read_by_count": 1,
      "is_edited": false,
      "is_deleted": false,
      "is_mine": false,
      "created_at": "2026-07-05T10:00:00Z",
      "updated_at": "2026-07-05T10:00:00Z"
    },
    {
      "id": "media-msg-uuid",
      "sender": { "id": "...", "name": "...", "avatar_url": "..." },
      "type": "media",
      "body": "Check this out",
      "reply_to": {
        "id": "parent-msg-uuid",
        "sender_name": "Alice",
        "type": "text",
        "body": "Original message"
      },
      "media": [
        {
          "id": "media-uuid",
          "url": "http://localhost:8000/media/chat_media/2026/07/05/photo.jpg",
          "media_type": "image",
          "file_name": "photo.jpg",
          "file_size": 245000,
          "order": 0
        }
      ],
      "reactions": {},
      "read_by_count": 0,
      "is_edited": false,
      "is_deleted": false,
      "is_mine": true,
      "created_at": "2026-07-05T09:58:00Z",
      "updated_at": "2026-07-05T09:58:00Z"
    },
    {
      "id": "call-msg-uuid",
      "sender": { "id": "...", "name": "...", "avatar_url": "..." },
      "type": "call",
      "body": "📞 Audio call • 2:35",
      "reply_to": null,
      "media": [],
      "reactions": {},
      "read_by_count": 0,
      "is_edited": false,
      "is_deleted": false,
      "is_mine": false,
      "created_at": "2026-07-05T09:00:00Z",
      "updated_at": "2026-07-05T09:00:00Z"
    }
  ],
  "errors": null,
  "meta": {
    "next_cursor": "2026-07-04T08:00:00Z|older-msg-uuid",
    "has_more": true,
    "page_size": 20,
    "timestamp": "..."
  }
}
```

**Message `type` values:** `text`, `media`, `doc`, `deleted`, `call`

---

### 2.6 Upload media / documents

Text messages use WebSocket — **only files** use this endpoint.

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/conversations/{conv_id}/messages/` |
| **Auth** | Required |
| **Content-Type** | `multipart/form-data` |

**Form fields (Postman → Body → form-data)**

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `files` | File | Yes | One or more files (repeat key for multiple) |
| `body` | Text | No | Caption |
| `reply_to_id` | Text | No | UUID of message being replied to |

**Supported types**

| Type | Extensions / MIME |
|------|-------------------|
| Image | jpeg, png, gif, webp — max `CHAT_IMAGE_MAX_SIZE_MB` (10) |
| Video | mp4, mov, webm — max `CHAT_VIDEO_MAX_SIZE_MB` (200)* |
| Document | pdf, doc, docx, xls, xlsx — max `CHAT_DOC_MAX_SIZE_MB` (50) |

\*Global Django upload cap may be lower — see `.env` `VIDEO_UPLOAD_MAX_SIZE_MB`.

**Response `201`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "id": "new-msg-uuid",
    "sender": {
      "id": "your-user-uuid",
      "name": "You",
      "avatar_url": ""
    },
    "type": "media",
    "body": "Optional caption",
    "reply_to": null,
    "media": [
      {
        "id": "media-uuid",
        "url": "http://localhost:8000/media/chat_media/2026/07/05/file.jpg",
        "media_type": "image",
        "file_name": "file.jpg",
        "file_size": 102400,
        "order": 0
      }
    ],
    "reactions": {},
    "read_by_count": 0,
    "is_edited": false,
    "is_deleted": false,
    "is_mine": true,
    "created_at": "2026-07-05T10:05:00Z",
    "updated_at": "2026-07-05T10:05:00Z"
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**After `201`:** send WebSocket `media_sent` (see §3) so other clients update instantly.

**Errors:** `404` not participant; `400` validation (unsupported type, size exceeded).

---

### 2.7 List message reactions

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/conversations/{conv_id}/messages/{msg_id}/reactions/` |
| **Auth** | Required |

**Query parameters**

| Param | Description |
|-------|-------------|
| `reaction` | Optional filter: `love`, `angry`, `haha`, `wow`, `sad`, `care` |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": [
    {
      "user_id": "user-uuid",
      "name": "Alice",
      "avatar_url": "https://...",
      "reaction": "love"
    }
  ],
  "errors": null,
  "meta": {
    "counts": { "love": 2, "haha": 1, "angry": 0, "wow": 0, "sad": 0, "care": 0 },
    "total": 3,
    "timestamp": "..."
  }
}
```

---

### 2.8 Shared media gallery

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/conversations/{conv_id}/media/` |
| **Auth** | Required |

Returns all images + videos in the conversation (not documents).

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": [
    {
      "id": "media-uuid",
      "url": "http://localhost:8000/media/chat_media/2026/07/05/photo.jpg",
      "media_type": "image",
      "file_name": "photo.jpg",
      "file_size": 245000,
      "order": 0
    }
  ],
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

---

## 3. Chat — WebSocket

### Connection

```
ws://localhost:8000/ws/chat/{conv_id}/?token={access_token}
```

| Check | Result |
|-------|--------|
| Invalid/missing token | Connection closed immediately |
| Not a participant | Connection closed |
| Valid | Connection accepted; `presence` broadcast to room |

**Postman:** New WebSocket Request → paste URL with real `conv_id` and token → Connect.

No initial message required from client.

---

### 3.1 Client → Server messages

Send JSON text frames. Unknown `type` is ignored.

#### Send text message

```json
{
  "type": "message",
  "body": "Hello!",
  "reply_to_id": null
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `body` | Yes | Non-empty after trim |
| `reply_to_id` | No | UUID string or null |

**Server action:** Saves to DB, broadcasts to room, sends FCM to other participants.

---

#### Broadcast after media upload

```json
{
  "type": "media_sent",
  "message_id": "uuid-from-post-201-response"
}
```

---

#### Typing indicator

```json
{ "type": "typing", "is_typing": true }
```

```json
{ "type": "typing", "is_typing": false }
```

---

#### Mark message read (DM)

```json
{
  "type": "read",
  "message_id": "msg-uuid"
}
```

---

#### Edit own text message

```json
{
  "type": "edit",
  "message_id": "msg-uuid",
  "body": "Updated text"
}
```

Only sender; only `type=text`; not deleted.

---

#### Delete own message

```json
{
  "type": "delete",
  "message_id": "msg-uuid"
}
```

---

#### Toggle reaction

```json
{
  "type": "react",
  "message_id": "msg-uuid",
  "reaction": "love"
}
```

**Valid reactions:** `love`, `angry`, `haha`, `wow`, `sad`, `care`

Same reaction again = remove. Different reaction = switch.

---

### 3.2 Server → Client messages

#### New message

```json
{
  "type": "message",
  "data": {
    "id": "msg-uuid",
    "sender": {
      "id": "sender-uuid",
      "name": "Jane",
      "avatar_url": ""
    },
    "type": "text",
    "body": "Hello!",
    "reply_to": null,
    "media": [],
    "reactions": {},
    "read_by_count": 0,
    "is_edited": false,
    "is_deleted": false,
    "created_at": "2026-07-05T10:00:00.000000+00:00",
    "updated_at": "2026-07-05T10:00:00.000000+00:00"
  }
}
```

---

#### Typing

```json
{
  "type": "typing",
  "user_id": "user-uuid",
  "is_typing": true
}
```

---

#### Presence (connect/disconnect)

```json
{
  "type": "presence",
  "user_id": "user-uuid",
  "is_online": true
}
```

```json
{
  "type": "presence",
  "user_id": "user-uuid",
  "is_online": false,
  "last_seen": "2026-07-05T10:30:00.123456+00:00"
}
```

---

#### Read receipt

```json
{
  "type": "read_receipt",
  "user_id": "reader-uuid",
  "message_id": "msg-uuid"
}
```

---

#### Message edited

```json
{
  "type": "message_edited",
  "data": {
    "id": "msg-uuid",
    "body": "Updated text",
    "is_edited": true
  }
}
```

---

#### Message deleted

```json
{
  "type": "message_deleted",
  "data": {
    "id": "msg-uuid",
    "type": "deleted",
    "body": "This message was deleted"
  }
}
```

---

#### Reaction updated

```json
{
  "type": "reaction_updated",
  "data": {
    "message_id": "msg-uuid",
    "reacted": true,
    "reaction": "love",
    "counts": { "love": 1, "haha": 0 }
  }
}
```

| `reacted` | Meaning |
|-----------|---------|
| `true` | Reaction added or changed |
| `false` | Reaction removed (`reaction` is null) |

---

## 4. Calls — HTTP endpoints

1:1 audio/video only. REST manages lifecycle; WebSocket relays WebRTC (§5).

### Call object shape (used in all call responses)

```json
{
  "id": "call-session-uuid",
  "conv_id": "conversation-uuid",
  "caller_id": "caller-user-uuid",
  "callee_id": "callee-user-uuid",
  "call_type": "audio",
  "status": "ringing",
  "duration": 0,
  "created_at": "2026-07-05T10:00:00.000000+00:00",
  "ended_at": null
}
```

**`status` values:** `ringing`, `accepted`, `connected`, `ended`, `missed`, `declined`, `cancelled`

---

### 4.1 Get TURN credentials

Required before WebRTC on the client. Postman can test this fully.

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/turn-credentials/` |
| **Auth** | Required |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "ice_servers": [
      {
        "urls": ["stun:103.149.105.4:3478"]
      },
      {
        "urls": [
          "turn:103.149.105.4:3478?transport=udp",
          "turn:103.149.105.4:3478?transport=tcp",
          "turns:103.149.105.4:5349?transport=tcp"
        ],
        "username": "1735689600:user-uuid",
        "credential": "base64-hmac-sha1-value"
      }
    ]
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

Pass `ice_servers` to Flutter `RTCPeerConnection` configuration.

---

### 4.2 Initiate call

Start call from **any screen** (profile, chat list, etc.).

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/calls/initiate/` |
| **Auth** | Required (caller) |

**Request body**
```json
{
  "callee_id": "target-user-uuid",
  "call_type": "video"
}
```

| Field | Required | Values |
|-------|----------|--------|
| `callee_id` | Yes | User UUID |
| `call_type` | No | `audio` (default) or `video` |

**Response `201`**
```json
{
  "success": true,
  "message": "Call ringing.",
  "data": {
    "call": {
      "id": "call-session-uuid",
      "conv_id": "dm-conv-uuid",
      "caller_id": "your-user-uuid",
      "callee_id": "target-user-uuid",
      "call_type": "video",
      "status": "ringing",
      "duration": 0,
      "created_at": "2026-07-05T10:00:00.000000+00:00",
      "ended_at": null
    },
    "caller": {
      "id": "your-user-uuid",
      "name": "Alice",
      "avatar_url": "https://..."
    },
    "callee": {
      "id": "target-user-uuid",
      "name": "Bob",
      "avatar_url": ""
    }
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**Side effects:** FCM high-priority push to callee; `incoming_call` on callee's notifications WS.

**Errors**

| Status | Message / cause |
|--------|-----------------|
| `400` | Missing `callee_id`; invalid `call_type`; cannot call yourself |
| `404` | User not found |
| `409` | User is busy on another call |

**Next steps (Postman / app):**
1. Save `data.call.id` as `call_id`
2. Connect `ws://.../ws/calls/{call_id}/?token=...` (caller token)
3. Callee accepts via §4.4

---

### 4.3 Get call status

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `{{base_url}}/calls/{call_id}/` |
| **Auth** | Required (caller or callee) |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "call": {
      "id": "call-session-uuid",
      "conv_id": "...",
      "caller_id": "...",
      "callee_id": "...",
      "call_type": "audio",
      "status": "accepted",
      "duration": 0,
      "created_at": "...",
      "ended_at": null
    }
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**Errors:** `404` if not found or not a party.

---

### 4.4 Accept call

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/calls/{call_id}/accept/` |
| **Auth** | Required (**callee only**) |
| **Body** | Empty `{}` or no body |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "call": {
      "id": "call-session-uuid",
      "status": "accepted",
      "call_type": "video",
      "duration": 0,
      "ended_at": null
    }
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**WebSocket broadcast** (call WS + notifications WS):
```json
{
  "type": "call_accepted",
  "call": { "id": "...", "status": "accepted", "..." : "..." },
  "accepted_by": "callee-user-uuid"
}
```

**Errors**

| Status | When |
|--------|------|
| `403` | Not the callee |
| `404` | Call not found |
| `409` | Not in `ringing` state |

---

### 4.5 Decline call

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/calls/{call_id}/decline/` |
| **Auth** | Required (**callee only**) |
| **Body** | Empty |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "call": {
      "id": "call-session-uuid",
      "status": "declined",
      "duration": 0,
      "ended_at": "2026-07-05T10:01:00.000000+00:00"
    }
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

Creates one `call` message in chat: `"📞 Video call declined"`.

**WebSocket:**
```json
{
  "type": "call_ended",
  "call": { "status": "declined", "..." : "..." }
}
```

---

### 4.6 Cancel call (caller — no answer)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/calls/{call_id}/cancel/` |
| **Auth** | Required (**caller only**) |
| **Body** | Empty |

**Response `200`** — `status` becomes `missed`.

Chat log: `"📞 Missed video call"`.

**Errors:** `403` not caller; `409` not ringing.

---

### 4.7 Report media connected (optional)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/calls/{call_id}/connected/` |
| **Auth** | Required (either party) |
| **Body** | Empty |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "call": {
      "id": "call-session-uuid",
      "status": "connected",
      "duration": 0,
      "ended_at": null
    }
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

**WebSocket (first time only):**
```json
{
  "type": "call_connected",
  "call": { "status": "connected", "..." : "..." }
}
```

**Errors:** `409` if call is not `accepted` or `connected`.

---

### 4.8 End call

**Single end point** — creates one chat log entry. Idempotent if already ended.

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `{{base_url}}/calls/{call_id}/end/` |
| **Auth** | Required (caller or callee) |

**Request body**
```json
{
  "duration": 125
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `duration` | No | Seconds talk time (default `0`) |

**Response `200`**
```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "call": {
      "id": "call-session-uuid",
      "status": "ended",
      "duration": 125,
      "ended_at": "2026-07-05T10:05:00.000000+00:00"
    }
  },
  "errors": null,
  "meta": { "timestamp": "..." }
}
```

Chat message example: `"📞 Audio call • 2:05"`

**WebSocket:**
```json
{
  "type": "call_ended",
  "call": { "status": "ended", "duration": 125, "..." : "..." }
}
```

**Errors:** `404`; `409` if call not in active state.

---

## 5. Calls — WebSocket

WebRTC signaling only. **Do not** send accept/decline/end here — use REST (§4).

### Connection

```
ws://localhost:8000/ws/calls/{call_id}/?token={access_token}
```

| Check | Result |
|-------|--------|
| Not caller/callee | Closed |
| Call already ended | Closed (code `4001`) |
| Active call | Accepted |

Connect **after** initiate (caller) or accept (callee).

---

### 5.1 Client → Server

#### WebRTC offer (caller, after accept)

```json
{
  "type": "offer",
  "sdp": {
    "type": "offer",
    "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n..."
  }
}
```

#### WebRTC answer (callee)

```json
{
  "type": "answer",
  "sdp": {
    "type": "answer",
    "sdp": "v=0\r\no=- 789012 2 IN IP4 127.0.0.1\r\n..."
  }
}
```

#### ICE candidate (both peers, trickle)

```json
{
  "type": "ice_candidate",
  "candidate": {
    "candidate": "candidate:842163049 1 udp 1677729535 192.168.1.5 54321 typ srflx",
    "sdpMid": "0",
    "sdpMLineIndex": 0
  }
}
```

#### Keepalive

```json
{ "type": "ping" }
```

**Server responds:**
```json
{ "type": "pong" }
```

> Postman can send/receive these JSON frames. Real SDP comes from `flutter_webrtc`, not hand-written.

---

### 5.2 Server → Client

Relayed from peer — **ignore frames where `sender_id` is your own user id**.

#### Offer / answer / ICE

Same shape as client → server, plus `sender_id`:

```json
{
  "type": "offer",
  "sdp": { "type": "offer", "sdp": "..." },
  "sender_id": "peer-user-uuid"
}
```

```json
{
  "type": "answer",
  "sdp": { "type": "answer", "sdp": "..." },
  "sender_id": "peer-user-uuid"
}
```

```json
{
  "type": "ice_candidate",
  "candidate": { "candidate": "...", "sdpMid": "0", "sdpMLineIndex": 0 },
  "sender_id": "peer-user-uuid"
}
```

#### Lifecycle (from REST actions)

```json
{
  "type": "call_accepted",
  "call": { "id": "...", "status": "accepted", "..." : "..." },
  "accepted_by": "callee-user-uuid"
}
```

```json
{
  "type": "call_connected",
  "call": { "id": "...", "status": "connected", "..." : "..." }
}
```

```json
{
  "type": "call_ended",
  "call": { "id": "...", "status": "ended", "duration": 125, "..." : "..." }
}
```

---

## 6. Notifications WebSocket (incoming call)

Connect once after login — receives social notifications **and** call events when app is open.

### Connection

```
ws://localhost:8000/ws/notifications/?token={access_token}
```

No client messages required (listen only).

---

### Server → Client

#### Incoming call (when someone calls you)

```json
{
  "type": "incoming_call",
  "call": {
    "id": "call-session-uuid",
    "conv_id": "conv-uuid",
    "caller_id": "caller-uuid",
    "callee_id": "your-user-uuid",
    "call_type": "video",
    "status": "ringing",
    "duration": 0,
    "created_at": "...",
    "ended_at": null
  },
  "caller": {
    "id": "caller-uuid",
    "name": "Alice",
    "avatar_url": "https://..."
  }
}
```

#### Call accepted

```json
{
  "type": "call_accepted",
  "call": { "status": "accepted", "..." : "..." },
  "accepted_by": "callee-user-uuid"
}
```

#### Call ended

```json
{
  "type": "call_ended",
  "call": { "status": "ended", "duration": 60, "..." : "..." }
}
```

#### Social notification (existing)

```json
{
  "type": "notification_event",
  "event": "new",
  "data": {
    "id": "notification-uuid",
    "event": "reaction",
    "message": "Alice reacted to your post.",
    "actor": { "id": "...", "name": "...", "avatar_url": "..." },
    "unread_count": 3
  }
}
```

---

## 7. Postman test flows

### Flow A — Chat text (two users)

1. **User A** — `POST /login/` → save `access_token_A`
2. **User B** — `POST /login/` → save `access_token_B`
3. **User A** — `POST /conversations/` `{ "user_id": "<B's uuid>" }` → save `conv_id`
4. **User A** — WebSocket connect `ws/chat/{conv_id}/?token=A`
5. **User B** — WebSocket connect same URL with token B
6. **User A** — WS send `{ "type": "message", "body": "Hi B" }`
7. **User B** — WS receives `{ "type": "message", "data": { ... } }`
8. **User B** — `GET /conversations/{conv_id}/messages/` → verify in history

### Flow B — Chat media

1. Steps 1–3 from Flow A
2. **User A** — `POST /conversations/{conv_id}/messages/` (form-data: `files` = image)
3. Copy `data.id` from 201 response
4. **User A** — WS `{ "type": "media_sent", "message_id": "<id>" }`
5. **User B** (WS connected) — receives full message in `{ "type": "message", "data": ... }`

### Flow C — Full call (REST + WS, no real audio)

Use two Postman tabs or two machines.

| Step | Actor | Action |
|------|-------|--------|
| 1 | A | `GET /turn-credentials/` |
| 2 | A | `POST /calls/initiate/` `{ "callee_id": "<B>", "call_type": "audio" }` → save `call_id` |
| 3 | B | WS connect `ws/notifications/?token=B` → receive `incoming_call` |
| 4 | A | WS connect `ws/calls/{call_id}/?token=A` |
| 5 | B | `POST /calls/{call_id}/accept/` |
| 6 | A | WS receives `call_accepted` |
| 7 | A | WS send `{ "type": "offer", "sdp": { "type": "offer", "sdp": "v=0..." } }` |
| 8 | B | WS connect `ws/calls/{call_id}/?token=B` → receives `offer` |
| 9 | B | WS send `{ "type": "answer", "sdp": { ... } }` |
| 10 | A | WS receives `answer` |
| 11 | Either | `POST /calls/{call_id}/connected/` |
| 12 | Either | `POST /calls/{call_id}/end/` `{ "duration": 30 }` |
| 13 | Both | WS receives `call_ended`; `GET /conversations/{conv_id}/messages/` shows call log |

### Flow D — Decline call

1. A initiates (step 2 above)
2. B → `POST /calls/{call_id}/decline/`
3. Verify `status: declined` and chat history

### Flow E — Missed call

1. A initiates
2. A → `POST /calls/{call_id}/cancel/` (or wait 45s for server auto-miss)
3. Verify `status: missed`

---

## 8. Architecture overview

```
Flutter app
    │ REST (chat list, upload, call initiate/accept/end)
    │ WS   (chat messages, WebRTC signaling)
    │ FCM  (wake phone for messages + calls)
    ▼
Django + Channels + Redis
    │
    ├── PostgreSQL (messages, calls, conversations)
    └── CoTURN (STUN/TURN — media relay, not through Django)
```

**Signaling** = small JSON (who is calling, SDP, ICE). **Media** = WebRTC audio/video bytes (P2P or via TURN).

---

## 9. Technologies explained

| Tech | Role in chat/calls |
|------|-------------------|
| **REST** | History, uploads, start/accept/end call — works when WS is closed |
| **Chat WS** | Real-time messages, typing, presence |
| **Call WS** | Relay WebRTC offer/answer/ICE between two peers |
| **Notifications WS** | Incoming call + social alerts while app is open |
| **FCM** | Wake callee when app is backgrounded |
| **CoTURN** | Relay media when P2P blocked by NAT/firewall |
| **WebRTC** | Actual voice/video (client-side only) |

---

## 10. Call state machine

```
initiate → RINGING
    ├─ accept → ACCEPTED → (optional /connected/) → CONNECTED → end → ENDED
    ├─ decline → DECLINED
    ├─ cancel / timeout → MISSED
    └─ end (from active) → ENDED
```

**Busy rule:** Cannot initiate if either user has status `ringing`, `accepted`, or `connected`.

**Ring timeout:** `CALL_RING_TIMEOUT_SECONDS` (default 45) — server auto-misses stale ringing calls.

---

## 11. FCM push payloads

Postman cannot receive FCM — register token on a real device at login.

### Chat message

```json
{
  "type": "chat_message",
  "conv_id": "conversation-uuid",
  "message_id": "message-uuid",
  "payload": "{...stringified message data...}"
}
```

### Incoming call (high priority)

```json
{
  "type": "incoming_call",
  "call_id": "call-session-uuid",
  "conv_id": "conversation-uuid",
  "caller_id": "caller-uuid",
  "caller_name": "Alice",
  "caller_avatar": "https://...",
  "call_type": "video"
}
```

---

## 12. Frontend developer checklist

### Chat
- [ ] Connect `/ws/chat/{conv_id}/` when opening a conversation
- [ ] Text via WS; media via REST + `media_sent`
- [ ] Handle FCM `chat_message` in background
- [ ] Connect `/ws/notifications/` after login

### Calling
- [ ] Call button → `POST /calls/initiate/` (no chat WS required)
- [ ] FCM + CallKit for `incoming_call` when app killed
- [ ] Notifications WS for `incoming_call` when app open
- [ ] `GET /turn-credentials/` before `RTCPeerConnection`
- [ ] Connect `/ws/calls/{call_id}/` for offer/answer/ICE
- [ ] UI: Calling → Connecting (ICE state) → Connected
- [ ] Hang up via `POST /calls/{id}/end/` only
- [ ] ICE restart on network change (client-side)

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `TURN_HOST` | — | STUN/TURN server host |
| `TURN_SECRET` | — | Must match `coturn/turnserver.conf` |
| `CALL_RING_TIMEOUT_SECONDS` | `45` | Auto-miss ringing calls |
| `CHAT_IMAGE_MAX_SIZE_MB` | `10` | Chat image upload limit |
| `CHAT_VIDEO_MAX_SIZE_MB` | `200` | Chat video upload limit |
| `CHAT_DOC_MAX_SIZE_MB` | `50` | Chat document upload limit |
