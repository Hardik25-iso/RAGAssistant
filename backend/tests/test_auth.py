from tests.conftest import register


def test_register_login_me(client):
    r = client.post("/api/auth/register",
                    json={"name": "Asha", "email": "asha@mail.com", "password": "Password123"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "student"

    r = client.post("/api/auth/login", json={"email": "ASHA@mail.com", "password": "Password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "asha@mail.com"


def test_duplicate_email_rejected(client):
    body = {"name": "Dup", "email": "dup@mail.com", "password": "Password123"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_weak_password_rejected(client):
    r = client.post("/api/auth/register", json={"name": "W", "email": "w@mail.com", "password": "short"})
    assert r.status_code == 422


def test_wrong_password_generic_error(client):
    r = client.post("/api/auth/login", json={"email": "nobody@mail.com", "password": "Password123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_requires_token(client):
    assert client.get("/api/subjects").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/api/subjects", headers=bad).status_code == 401


def test_refresh_token_cannot_be_used_as_access(client):
    r = client.post("/api/auth/register",
                    json={"name": "Ravi", "email": "r@mail.com", "password": "Password123"})
    refresh = r.json()["refresh_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh}"}).status_code == 401
    r2 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200 and r2.json()["access_token"]


def test_cannot_self_register_as_admin(client):
    r = client.post("/api/auth/register",
                    json={"name": "Xena", "email": "x@mail.com", "password": "Password123", "role": "admin"})
    assert r.json()["user"]["role"] == "student"


def test_rbac_admin_vs_student(client, admin):
    student = register(client)
    assert client.get("/api/admin/stats", headers=student).status_code == 403
    assert client.get("/api/admin/stats", headers=admin).status_code == 200
    # admins have no access to student content routes
    assert client.get("/api/subjects", headers=admin).status_code == 403
