"""Security tests, including the key demo: Student A cannot see Student B's data."""
import io
import zipfile

from tests.conftest import make_pdf, make_pptx, new_subject, upload

SECRET = "Student B secret topic: quantum flux capacitor calibration procedure"


def test_student_isolation(client, student, student_b):
    # Student B uploads private notes
    sid_b = new_subject(client, student_b, "Physics")
    doc_b = upload(client, student_b, sid_b, "secret.pdf", make_pdf([SECRET])).json()

    # Student A cannot list, read, download, delete or chat over B's subject/document
    assert client.get(f"/api/documents?subject_id={sid_b}", headers=student).status_code == 404
    assert client.get(f"/api/documents/{doc_b['id']}", headers=student).status_code == 404
    assert client.get(f"/api/documents/{doc_b['id']}/download", headers=student).status_code == 404
    assert client.delete(f"/api/documents/{doc_b['id']}", headers=student).status_code == 404
    assert client.patch(f"/api/subjects/{sid_b}", json={"name": "x"}, headers=student).status_code == 404
    r = client.post("/api/chat/ask", json={"subject_id": sid_b, "question": "flux capacitor"}, headers=student)
    assert r.status_code == 404

    # Even passing B's doc id into A's own subject retrieves nothing of B's
    sid_a = new_subject(client, student, "Physics A")
    r = client.post("/api/chat/ask",
                    json={"subject_id": sid_a, "question": "flux capacitor calibration", "doc_ids": [doc_b["id"]]},
                    headers=student)
    assert r.status_code == 404
    r = client.post("/api/chat/ask", json={"subject_id": sid_a, "question": "flux capacitor calibration"},
                    headers=student)
    assert "flux" not in r.json()["answer"].lower()
    assert r.json()["citations"] == []

    # B still sees their own document
    assert client.get(f"/api/documents/{doc_b['id']}", headers=student_b).status_code == 200


def test_chat_session_isolation(client, student, student_b):
    sid = new_subject(client, student_b, "Bio")
    upload(client, student_b, sid, "bio.pdf", make_pdf(["Cells are the basic unit of life"]))
    s = client.post("/api/chat/ask", json={"subject_id": sid, "question": "what are cells"},
                    headers=student_b).json()["session_id"]
    assert client.get(f"/api/chat/sessions/{s}/messages", headers=student).status_code == 404


def test_admin_cannot_read_documents(client, student, admin):
    sid = new_subject(client, student, "Admin test")
    doc = upload(client, student, sid, "a.pdf", make_pdf(["private"])).json()
    assert client.get(f"/api/documents/{doc['id']}", headers=admin).status_code == 403
    stats = client.get("/api/admin/stats", headers=admin).json()
    assert stats["documents"] >= 1 and "content" not in str(stats)


def test_rejects_wrong_signature(client, student):
    sid = new_subject(client, student, "Files1")
    r = upload(client, student, sid, "evil.pdf", b"MZ\x90\x00 this is an exe")
    assert r.status_code == 415


def test_rejects_extension_mismatch(client, student):
    sid = new_subject(client, student, "Files2")
    r = upload(client, student, sid, "notes.pptx", make_pdf(["hello"]))
    assert r.status_code == 400


def test_rejects_legacy_ppt(client, student):
    sid = new_subject(client, student, "Files3")
    r = upload(client, student, sid, "old.ppt", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)
    assert r.status_code == 400 and ".pptx" in r.json()["detail"]


def test_rejects_plain_zip_named_pptx(client, student):
    sid = new_subject(client, student, "Files4")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    r = upload(client, student, sid, "fake.pptx", buf.getvalue())
    assert r.status_code == 400


def test_rejects_zip_bomb(client, student):
    sid = new_subject(client, student, "Files5")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("ppt/presentation.xml", "<x/>")
        z.writestr("ppt/bomb.bin", b"\x00" * (60 * 1024 * 1024))
    r = upload(client, student, sid, "bomb.pptx", buf.getvalue())
    assert r.status_code == 400 and "zip bomb" in r.json()["detail"]


def test_rejects_oversized(client, student):
    sid = new_subject(client, student, "Files6")
    big = b"%PDF-1.4\n" + b"0" * (21 * 1024 * 1024)
    assert upload(client, student, sid, "big.pdf", big).status_code == 413


def test_filename_sanitized(client, student):
    sid = new_subject(client, student, "Files7")
    r = upload(client, student, sid, "../../etc/<script>.pptx", make_pptx([("T", "b", "n")]))
    assert r.status_code == 201
    assert r.json()["filename"] == "_script_.pptx"


def test_security_headers_and_request_id(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Request-ID"] and r.headers["X-Instance-ID"]


def test_errors_are_json_without_internals(client, student):
    r = client.post("/api/subjects", json={"name": ""}, headers=student)
    assert r.status_code == 422 and r.json()["detail"] == "Invalid request" and "request_id" in r.json()
    r = client.get("/api/documents/not-a-real-id", headers=student)
    assert r.status_code == 404 and "Traceback" not in r.text
