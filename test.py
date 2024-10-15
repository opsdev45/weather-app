import pytest
import requests


def test_runner():
    """Get request to check if the site available"""
    
    response = requests.request("GET", f"http://127.0.0.1:8000/")
    assert response.status_code == 200

if __name__ == "__main__":
    print("Test python available")
    test_runner()
    
