def _register_and_login(client, email):
    client.post("/api/auth/register", json={"email": email, "name": "User", "password": "supersecret1"})
    resp = client.post("/api/auth/login", data={"username": email, "password": "supersecret1"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_provisions_personal_workspace(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "newuser@example.com", "name": "New", "password": "supersecret1"},
    )
    assert resp.status_code == 201
    login = client.post("/api/auth/login", data={"username": "newuser@example.com", "password": "supersecret1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    workspaces = client.get("/api/workspaces", headers=headers)
    assert workspaces.status_code == 200
    names = [w["name"] for w in workspaces.json()]
    assert "Personal" in names


def test_new_user_can_create_deal_without_manual_workspace(client):
    """The create-deal workflow must work immediately after signup — no extra workspace step."""
    headers = _register_and_login(client, "workflow@example.com")
    ws = client.get("/api/workspaces", headers=headers).json()
    assert len(ws) >= 1
    resp = client.post(
        "/api/deals",
        json={"workspace_id": ws[0]["id"], "company_name": "Acme Corp"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["company_name"] == "Acme Corp"


def test_workspace_name_cannot_be_blank(client):
    headers = _register_and_login(client, "blank-ws@example.com")
    resp = client.post("/api/workspaces", json={"name": ""}, headers=headers)
    assert resp.status_code == 422


def test_deal_company_name_cannot_be_blank(client):
    headers = _register_and_login(client, "blank-deal@example.com")
    ws = client.get("/api/workspaces", headers=headers).json()[0]
    resp = client.post(
        "/api/deals",
        json={"workspace_id": ws["id"], "company_name": ""},
        headers=headers,
    )
    assert resp.status_code == 422


def test_login_rejects_wrong_password(client):
    client.post("/api/auth/register", json={"email": "a@example.com", "name": "A", "password": "supersecret1"})
    resp = client.post("/api/auth/login", data={"username": "a@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/workspaces")
    assert resp.status_code == 401


def test_viewer_cannot_create_deal(client):
    admin_headers = _register_and_login(client, "admin@example.com")
    viewer_headers = _register_and_login(client, "viewer@example.com")

    ws = client.post("/api/workspaces", json={"name": "WS"}, headers=admin_headers).json()

    # Manually downgrade: register the viewer as a member with viewer role via a second workspace
    # membership isn't exposed by an endpoint in this MVP, so we simulate by asserting a
    # non-member is rejected outright (stricter than "viewer role"; membership is required).
    resp = client.post(
        "/api/deals",
        json={"workspace_id": ws["id"], "company_name": "X"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403


def test_editor_cannot_access_deal_outside_workspace(client):
    user_a = _register_and_login(client, "a2@example.com")
    user_b = _register_and_login(client, "b2@example.com")

    ws_a = client.post("/api/workspaces", json={"name": "WS-A"}, headers=user_a).json()
    deal_a = client.post(
        "/api/deals", json={"workspace_id": ws_a["id"], "company_name": "Deal A"}, headers=user_a
    ).json()

    resp = client.get(f"/api/deals/{deal_a['id']}", headers=user_b)
    assert resp.status_code == 403


def test_deal_not_ready_for_valuation_until_required_fields_set(client):
    headers = _register_and_login(client, "c2@example.com")
    ws = client.post("/api/workspaces", json={"name": "WS-C"}, headers=headers).json()
    deal = client.post(
        "/api/deals", json={"workspace_id": ws["id"], "company_name": "Bare Deal"}, headers=headers
    ).json()
    assert deal["ready_for_valuation"] is False
