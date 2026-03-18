# Product Requirements Document: Authentication

## Overview

The Kessler Space Object Registry application currently exposes all data and admin functionality with no access control. Any user who can reach the application URL can view satellite data, browse graphs, and — critically — trigger server-side maintenance scripts via the Admin page. Authentication is needed to restrict access to authorized users only.

## Goals

- Prevent unauthorized users from viewing any application data.
- Protect the Admin page (which can execute scripts on the server) from unauthenticated or unauthorized access.
- Introduce the minimum viable security layer with the least complexity, consistent with the existing stack.

## Non-Goals

- Multi-user account management (registration, password reset, user profiles).
- Role-based access control (RBAC) beyond distinguishing "authenticated" vs. "not authenticated".
- OAuth / third-party identity providers (Google, GitHub, etc.).
- Persistent session storage or remember-me functionality (session ends when the browser tab closes).

## User Stories

### US-1: Login to access the application
> As a user, I want to enter a password (and optionally a username) so that I can access the satellite registry.

**Acceptance criteria:**
- The application shows a login screen instead of any data when the user is not authenticated.
- Valid credentials grant access to the full application.
- Invalid credentials display a clear error message.
- The login screen is the only page accessible without authentication.

### US-2: Session persists within the browser session
> As a user, I want to stay logged in while my browser tab is open so that I don't have to re-authenticate on every page navigation.

**Acceptance criteria:**
- After a successful login, the user is not prompted again during the same browser session.
- Closing and reopening the browser (or tab) requires re-authentication.

### US-3: Logout
> As a user, I want to be able to log out so that others using the same computer cannot access the application after me.

**Acceptance criteria:**
- A visible logout action is available from within the application.
- After logout, the user is returned to the login screen and cannot access data without re-authenticating.

### US-4: Admin page is protected
> As an operator, I want the Admin page (which can run server scripts) to be inaccessible to unauthenticated users so that server integrity is maintained.

**Acceptance criteria:**
- The Admin page is not reachable without first authenticating.
- All API endpoints (including `/v2/admin/...`) return HTTP 401 for unauthenticated requests.

### US-5: Credentials are configurable via environment variables
> As an operator, I want to configure credentials via environment variables so that I can manage access without code changes and keep secrets out of the repository.

**Acceptance criteria:**
- The application uses credentials (at minimum a password; optionally a username) sourced from environment variables.
- Default/fallback credentials are not hard-coded in a way that is safe for production (i.e., the app should refuse to start or warn loudly if no credentials are configured).
- The `.env.example` file documents the required variables.

## Scope

### In scope
- A login screen rendered by the React frontend before the main application is shown.
- All existing API endpoints require authentication; unauthenticated requests receive HTTP 401.
- Credentials are stored in environment variables on the server side.
- The authenticated session is maintained client-side for the duration of the browser session (sessionStorage or in-memory).
- A logout control in the application header.

### Out of scope
- Database-backed user accounts.
- Email-based flows (forgot password, invite).
- Fine-grained per-route authorization.
- Audit logging of authenticated actions.

## Assumptions

1. **Single shared password** (or username + password pair) is sufficient. There is no need for individual user accounts at this stage.
2. **Session duration = browser tab lifetime** is acceptable. No persistent "remember me" cookie is required.
3. The application is accessed over HTTPS in production; transmitting credentials over plain HTTP in development is acceptable.
4. There is no existing user store (database table, LDAP, etc.) that needs to be integrated.

## Success Criteria

- No application data is visible without a successful login.
- The Admin page and all `/v2/admin/` API endpoints return 401 to unauthenticated callers.
- Login and logout work correctly in a standard browser.
- Credentials are sourced entirely from environment variables.
- No new production dependencies are required beyond what FastAPI already provides (i.e., `python-jose` / `passlib` may be added if needed for JWT, but the simplest built-in approach is preferred).
