from fastapi.testclient import TestClient

from app.main import app, retriever

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_empty_chat_message_is_rejected():
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_knowledge_scope_question_returns_dataset_count():
    response = client.post(
        "/api/chat", json={"message": "How many real estate information do you have?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "knowledge_scope"
    assert str(len(retriever.records)) in data["answer"]
