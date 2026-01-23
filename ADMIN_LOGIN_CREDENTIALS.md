# Admin Login Credentials

## ✅ Working Credentials

**Email:** `admin@failstate.in`  
**Password:** `FailState@2026!Secure#Admin`

## Database Hash

If you need to reset the password in the database, use this SQL:

```sql
UPDATE admins 
SET password_hash = '$2b$12$hVw73qD.xNtuh2eFR2cTNe66PXPdmzv0wIUKiSYf9t19YIaqEmTbK',
    updated_at = NOW()
WHERE email = 'admin@failstate.in';
```

## Login Endpoints

**Local:** `POST http://localhost:8000/admin/login`  
**Production:** `POST https://api.failstate.in/admin/login`

## Example Login Request

```bash
curl -X POST https://api.failstate.in/admin/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@failstate.in",
    "password": "FailState@2026!Secure#Admin"
  }'
```

## Response Format

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "admin": {
    "id": "...",
    "email": "admin@failstate.in",
    "username": "admin",
    "full_name": "FailState Administrator",
    "is_super_admin": true
  }
}
```

## Using the Token

Include the access token in subsequent requests:

```bash
curl -X GET https://api.failstate.in/admin/dashboard \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Security Notes

⚠️ **IMPORTANT:** Change this password after first login in production!

The admin system includes:
- ✅ Bcrypt password hashing (12 rounds)
- ✅ JWT tokens with 12-hour expiration
- ✅ Complete audit logging of all admin actions
- ✅ Separate admin authentication from regular users
- ✅ Super admin role support

---

**Last Updated:** January 23, 2026  
**Hash Generated:** Locally verified and tested
