# StayFlow — Supabase Monolith

A single Flask application for hotel discovery, guest booking, manager operations and administration. This revision removes SQLite and uses **Supabase Auth + Supabase PostgreSQL**.

## What changed

- Responsive StayFlow UI with improved public discovery, authentication, and guest onboarding.
- Guests can create their own accounts at `/register`; new self-service accounts are always assigned the `guest` role.
- Authentication is handled by Supabase Auth (email/password).
- Authorization remains server-side in Flask (`admin`, `manager`, `guest`) so changing browser data cannot elevate a role.
- Application data is stored in Supabase PostgreSQL. `sqlite3` and `hotel_booking.db` are no longer used.
- Admin-created manager/admin/guest accounts are provisioned in Supabase Auth with the server-only service-role key.
- `supabase/schema.sql` contains the database schema, constraints, indexes, and RLS enablement.

## Supabase setup

1. Create a Supabase project.
2. Open **SQL Editor** and run `supabase/schema.sql`.
3. In **Authentication > Providers**, keep Email enabled. Choose whether email confirmation is required for guest signup.
4. Copy `.env.example` to `.env` and fill `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `DATABASE_URL` from your Supabase project settings/connect dialog.
5. Keep the service-role key server-side only. Never place it in templates, frontend JavaScript, Git, or a public deployment variable exposed to clients.

The schema enables RLS and defines no browser-facing table policies because this Flask server is the trusted data boundary and connects to Postgres server-side. Supabase Auth remains the identity provider.

## Install and run

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.

## First admin

Create an Auth user in the Supabase dashboard (email/password), copy that user's UUID, then run this once in SQL Editor:

```sql
insert into public.users(auth_user_id, username, role, email)
values ('AUTH-USER-UUID', 'admin', 'admin', 'admin@example.com');
```

After that, the admin dashboard can create additional manager/admin accounts. Public registration can only create `guest` profiles.

## Demo data

After the schema and environment variables are configured:

```bash
python seed_demo_data.py
```

This adds sample hotels/rooms only; it does not create insecure default passwords.

## Security notes

Use strong random `SESSION_SECRET` and `JWT_SECRET` values in production, HTTPS, a restricted database credential, and Supabase's recommended production email/redirect settings. Uploaded hotel/room images are stored locally in `uploads/`; Supabase Storage can be added later if you want stateless/cloud media storage too.

## Authentication repair / role redirects (updated build)

This build avoids naming the local integration module `supabase_auth.py` because that name collides with the package used internally by the Supabase Python SDK. The local integration is `stayflow_auth.py`.

After running `supabase/schema.sql`, configure `.env` from `.env.example`. Use the Supabase **Session pooler** DATABASE_URL when your network does not support the direct IPv6 database endpoint.

Role routing after successful login is server-side:
- `admin` -> `/admin/dashboard`
- `manager` -> `/manager/dashboard`
- `guest` -> `/guest/dashboard`

Public `/register` can only create a `guest`. Admin and manager accounts must be created by an existing admin, or the first admin can be bootstrapped with:

    python auth_tools.py bootstrap-admin

If an older failed signup left a user in Supabase Authentication but not in `public.users`, either sign in normally (this build repairs missing guest profiles after valid authentication), or run:

    python auth_tools.py repair

Seed the included demo hotels/rooms/images with:

    python seed_demo_data.py

Security: never commit `.env`; rotate any service-role key or database password that has been shared publicly.

## Demo users created by the seed
`python seed_demo_data.py` now creates or repairs and confirms these Supabase Auth users, synchronizes their `public.users` roles, and assigns the demo manager to the first hotel:

- `arunravikanth20@gmail.com` — admin
- `ravikanth0920@gmail.com` — manager
- `arunravikanth123@gmail.com` — guest

Passwords are read from `DEMO_ADMIN_PASSWORD`, `DEMO_MANAGER_PASSWORD`, and `DEMO_GUEST_PASSWORD` in `.env`. The `.env.example` values are only development defaults; change them for any shared or deployed environment. The seed resets these three demo users to the configured passwords and confirms their emails.
