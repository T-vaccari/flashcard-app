from fastapi.testclient import TestClient
from backend.main import app
from backend.services import FlashcardService
import os

client = TestClient(app)

def test_api_flow():
    # 1. Get Stats (checks CSV load)
    response = client.get("/stats")
    assert response.status_code == 200
    stats = response.json()
    print("Initial Stats:", stats)
    assert "total_cards" in stats
    
    # 2. Start Request (Due)
    # Note: We might not have due cards depending on CSV state, likely we do or don't.
    # Let's try 'cram' to ensure we get cards.
    response = client.post("/study/start", json={"mode": "cram"})
    assert response.status_code == 200
    print("Start Study (Cram):", response.json())
    
    # 3. Get Next Card
    response = client.get("/study/next")
    assert response.status_code == 200
    data = response.json()
    print("Next Card Data:", data.keys())
    
    if not data.get("finished"):
        card = data["card"]
        card_id = card["id"]
        print(f"Reviewing card {card_id}")
        
        # 4. Review
        response = client.post(f"/study/review/{card_id}", json={"quality": 4})
        assert response.status_code == 200
        print("Review Response:", response.json())

    # 5. Add Card
    new_card = {
        "id": "temp", "front": "TestQ", "back": "TestA", "chapter": 1,
        "interval": 0, "ease_factor": 2.5, "repetitions": 0
    }
    response = client.post("/cards", json=new_card)
    assert response.status_code == 200
    created_card = response.json()
    created_id = created_card["id"]
    print("Created Card:", created_id)
    
    # 6. Delete Card
    response = client.delete(f"/cards/{created_id}")
    assert response.status_code == 200
    print("Deleted Card")

if __name__ == "__main__":
    test_api_flow()
