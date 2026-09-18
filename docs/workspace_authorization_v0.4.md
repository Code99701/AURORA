# Workspace Authorization Foundation v0.4

Workspace Authorization Foundation v0.4 establishes the smallest data-isolation boundary AURORA needs before document ingestion begins. It is intentionally not a team-management or enterprise collaboration system.

## Why AURORA needs workspaces

Authentication answers, “Who is making this request?” Authorization answers, “What is this user allowed to access?”

Logging in alone must never provide access to every document in AURORA. Future documents, chunks, embeddings, conversations, citations, and research results will carry a `workspace_id`. The workspace membership boundary will therefore keep one user’s research data out of another user’s retrieval and generation context.

## Database relationships

```text
User
 ├─ creates ───────────────> Workspace
 └─ has WorkspaceMembership ─> Workspace
```

`Workspace` stores a UUID, name, optional description, timestamps, and the creating user’s ID. A UUID makes public identifiers difficult to guess, but UUIDs are not authorization: every request still checks membership.

`WorkspaceMembership` connects one user to one workspace and stores either the `OWNER` or `MEMBER` role. A database uniqueness constraint permits only one membership for each `(workspace_id, user_id)` pair. Foreign keys preserve referential integrity, and deleting a workspace cascades to its memberships.

Creating a workspace and its OWNER membership occurs in one database transaction:

```text
authenticated user
  -> create workspace
  -> flush workspace UUID
  -> create OWNER membership
  -> commit both changes
```

If any step fails, neither partial record is committed.

## Roles

- `OWNER` can view, update, and delete the workspace.
- `MEMBER` can view the workspace but cannot update or delete it.

There is no membership-management API in v0.4. Roles cannot be supplied through workspace create/update requests, which prevents clients from assigning or escalating privileges. Invitation flows and advanced RBAC are deferred.

## Authorization request flow

Workspace routes reuse the existing session authentication dependency:

```text
HttpOnly cookie
  -> get_current_user()
  -> parse workspace UUID
  -> get_current_workspace()
  -> query workspace joined to this user's membership
  -> require_workspace_member() or require_workspace_owner()
  -> route handler
  -> workspace service
```

The reusable dependencies are:

- `get_current_user()` authenticates the server-side session.
- `get_current_workspace()` returns a workspace only when the current user belongs to it.
- `require_workspace_member()` establishes read access.
- `require_workspace_owner()` additionally checks the membership role before modification.

Route handlers validate HTTP input and delegate business operations to `app/services/workspace.py`.

## Unauthorized-resource policy

AURORA uses these consistent responses:

- `401 Unauthorized`: authentication is missing or invalid.
- `404 Not Found`: the workspace does not exist **or** the authenticated user is not a member.
- `403 Forbidden`: the user is a member and may view the workspace, but lacks the OWNER role required to change or delete it.

Returning the same 404 for missing and non-member resources helps prevent IDOR enumeration. Knowing or guessing another workspace UUID never grants access.

## API endpoints

| Endpoint | Required access | Behavior |
|---|---|---|
| `POST /api/v1/workspaces` | Authenticated | Creates a workspace and OWNER membership |
| `GET /api/v1/workspaces` | Authenticated | Lists only the user’s memberships |
| `GET /api/v1/workspaces/{workspace_id}` | MEMBER or OWNER | Returns one authorized workspace |
| `PATCH /api/v1/workspaces/{workspace_id}` | OWNER | Changes only name and/or description |
| `DELETE /api/v1/workspaces/{workspace_id}` | OWNER | Deletes the workspace and cascades memberships |

Public responses expose the workspace UUID, name, description, timestamps, and creator ID. They do not return membership internals or SQLAlchemy objects directly; Pydantic response schemas control serialization.

## Security considerations

- All endpoints require the existing opaque-session authentication.
- Workspace lookup includes the authenticated user’s membership in the SQL query.
- OWNER checks read the stored membership role; request bodies cannot set it.
- Strict Pydantic schemas reject unknown fields, defending against mass assignment.
- Database constraints reject duplicate memberships and roles outside OWNER/MEMBER.
- Foreign keys prevent orphan relationships.
- Workspace deletion cascades only its membership rows; users and sessions are preserved.
- UUID identifiers reduce predictability but never replace authorization checks.

The automated suite verifies creation, automatic ownership, filtered listing, member access, cross-workspace denial, OWNER-only updates/deletes, role escalation rejection, duplicate membership rejection, cascading deletion, unauthenticated denial, and migration upgrade/downgrade/re-upgrade.

## Scope boundary

v0.4 creates the isolation foundation only. It does not implement invitations, membership administration, documents, extraction, chunking, embeddings, retrieval, RAG, citations, multilingual processing, or frontend screens.
