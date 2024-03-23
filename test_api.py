import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import json
from pandas import DataFrame
from TraderAgent.trader_agent import app, Credentials, Session  # Ensure this path is correct

client = TestClient(app)

@pytest.mark.asyncio
async def test_check_credentials():
    chat_id = "123456"

    # Scenario 1: Credentials found
    with patch('TraderAgent.trader_agent.r.hgetall', return_value={"username": '"testuser"', "password": '"testpass"'}) as mock_redis:
        response = client.get(f"/checkcredentials/{chat_id}")
        assert response.status_code == 200  # HTTP status code is always 200
        assert response.json() == {"username": "testuser", "password": "testpass", "status": 200}
        mock_redis.assert_called_once_with(chat_id)

    # Scenario 2: No credentials found
    with patch('TraderAgent.trader_agent.r.hgetall', return_value={}) as mock_redis:
        response = client.get(f"/checkcredentials/{chat_id}")
        assert response.status_code == 200  # HTTP status code is still 200
        assert response.json() == {"message": "No credentials found", "status": 404}  # Checking the JSON payload for the custom status
        mock_redis.assert_called_with(chat_id)

    # Scenario 3: Exception raised
    with patch('TraderAgent.trader_agent.r.hgetall', side_effect=Exception("Redis error")) as mock_redis:
        response = client.get(f"/checkcredentials/{chat_id}")
        assert response.status_code == 200  # HTTP status code remains 200
        assert response.json() == {"message": "Error retrieving credentials", "status": 500}  # JSON payload indicates an error
        mock_redis.assert_called_with(chat_id)


@pytest.mark.asyncio
async def test_verify_and_store_credentials():
    valid_credentials = {
        "api_key": "valid_api_key",
        "api_secret": "valid_api_secret",
        "chat_id": "123456"
    }

    invalid_credentials = {
        "api_key": "invalid_api_key",
        "api_secret": "invalid_api_secret",
        "chat_id": "123456"
    }

    # Scenario 1: Credentials Verified and Stored
    with patch('TraderAgent.trader_agent.tradeapi.REST') as mock_tradeapi, \
         patch('TraderAgent.trader_agent.r.hset', new_callable=AsyncMock) as mock_hset:
        mock_tradeapi.return_value.get_account.return_value = AsyncMock()  # Use AsyncMock for async operations
        response = client.post("/verifyandstorecredentials/", json=valid_credentials)
        assert response.status_code == 200
        assert response.json() == {"message": "Credentials verified, account is active and not restricted from trading.", "status": 200}
        mock_hset.assert_called()

    # Scenario 2: Invalid Credentials
    with patch('TraderAgent.trader_agent.tradeapi.REST', side_effect=Exception("Invalid credentials or access forbidden.")) as mock_tradeapi:
        response = client.post("/verifyandstorecredentials/", json=invalid_credentials)
        assert response.status_code == 200  # Assuming your endpoint structure always returns HTTP 200
        assert response.json() == {"message": "Invalid credentials or access forbidden.", "status": 404}

@pytest.mark.asyncio
async def test_check_ticker():
    valid_ticker = {"ticker": "AAPL"}
    invalid_ticker = {"ticker": "INVALID"}

    # Scenario 1: Ticker Exists
    with patch('TraderAgent.trader_agent.yf.Ticker') as mock_ticker:
        # Mock the history method to return a non-empty DataFrame
        mock_ticker.return_value.history.return_value = DataFrame({'Open': [1]})
        response = client.post("/check_ticker/", json=valid_ticker)
        assert response.status_code == 200
        assert response.json() == {"status": 200, "message": "Ticker exists"}

    # Scenario 2: Ticker Not Found
    with patch('TraderAgent.trader_agent.yf.Ticker') as mock_ticker:
        # Mock the history method to return an empty DataFrame
        mock_ticker.return_value.history.return_value = DataFrame()
        response = client.post("/check_ticker/", json=invalid_ticker)
        assert response.status_code == 200  # Assuming your endpoint structure always returns HTTP 200
        assert response.json() == {"status": 404, "message": "Ticker not found"}

    # Scenario 3: Exception Occurs
    with patch('TraderAgent.trader_agent.yf.Ticker', side_effect=Exception("Internal server error")) as mock_ticker:
        response = client.post("/check_ticker/", json=invalid_ticker)
        assert response.status_code == 200  # Assuming your endpoint structure always returns HTTP 200
        assert response.json() == {"status": 500, "message": "Internal server error"}

@pytest.mark.asyncio
async def test_store_and_start_new_session():
    valid_session = {
        "chat_id": "123456",
        "ticker": "AAPL",
        "amount_to_spend": "1000",
        "session_alive": True,
        "end_time": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    }
    insufficient_funds_session = valid_session.copy()
    insufficient_funds_session["amount_to_spend"] = "1000000"  # Large amount to ensure insufficient funds

    # Scenario 1: No Credentials Found
    with patch('TraderAgent.trader_agent.r.hgetall', return_value={}) as mock_redis:
        response = client.post("/store_and_start_new_session/", json=valid_session)
        assert response.status_code == 200  # Assuming HTTP 200 is always returned
        assert response.json() == {"message": "No credentials found", "status": 404}
        mock_redis.assert_called()

    # Scenario 2: Insufficient Funds
    with patch('TraderAgent.trader_agent.r.hgetall', return_value={"api_key": "valid", "api_secret": "valid"}), \
         patch('TraderAgent.trader_agent.tradeapi.REST') as mock_tradeapi:
        mock_tradeapi.return_value.get_account.return_value = MagicMock(cash="500")  # Less cash than amount_to_spend
        response = client.post("/store_and_start_new_session/", json=insufficient_funds_session)
        assert response.status_code == 200
        assert response.json() == {"status": 403, "message": "Insufficient funds"}

    # Scenario 3: Session Saved and Started Successfully
    with patch('TraderAgent.trader_agent.r.hgetall', return_value={"api_key": "valid", "api_secret": "valid"}), \
        patch('TraderAgent.trader_agent.tradeapi.REST') as mock_tradeapi, \
        patch('TraderAgent.trader_agent.r.hset', new_callable=AsyncMock) as mock_hset, \
        patch('TraderAgent.trader_agent.Alpaca') as mock_alpaca, \
        patch('TraderAgent.trader_agent.MLStrategy') as mock_ml_strategy, \
        patch('TraderAgent.trader_agent.trader.add_strategy', new_callable=AsyncMock) as mock_add_strategy, \
        patch('TraderAgent.trader_agent.trader.run_all_async', new_callable=AsyncMock) as mock_run_all_async, \
        patch('TraderAgent.trader_agent.check_and_stop_session', new_callable=AsyncMock) as mock_check_and_stop:

        # Setup mock objects and return values
        mock_tradeapi.return_value.get_account.return_value = MagicMock(cash="1500")
        mock_broker = MagicMock()
        mock_strategy = MagicMock()
        mock_alpaca.return_value = mock_broker
        mock_ml_strategy.return_value = mock_strategy

        response = client.post("/store_and_start_new_session/", json=valid_session)
        assert response.status_code == 200
        assert response.json() == {"status": 200, "message": "Session saved and started succesfully"} 

        # Additional assertions to ensure the mocks were called as expected
        mock_hset.assert_called()
        mock_add_strategy.assert_called_with(mock_strategy)
        mock_run_all_async.assert_called()
        mock_check_and_stop.assert_called()

    # Scenario 4: Internal Server Error
    with patch('TraderAgent.trader_agent.r.hgetall', side_effect=Exception("Internal server error")) as mock_redis:
        response = client.post("/store_and_start_new_session/", json=valid_session)
        assert response.status_code == 200  # Assuming HTTP 200 is always returned
        assert response.json() == {"status": 500, "message": "Internal server error"}
        mock_redis.assert_called()

@pytest.mark.asyncio
async def test_stop_session():
    session_data = {
        "chat_id": "123456",
        "ticker": "AAPL",
        "amount_to_spend": "1000",
        "session_alive": True,
        "end_time": "2023-01-01 12:00:00"
    }

    # Scenario 1: No Credentials Found
    with patch('TraderAgent.trader_agent.r.hgetall', return_value={}) as mock_redis:
        response = client.post("/stop_session/", json=session_data)
        assert response.status_code == 200
        assert response.json() == {"message": "No credentials found", "status": 404}
        mock_redis.assert_called_once_with(session_data["chat_id"])

     # Scenario 2: Session Stopped Successfully
    with patch('TraderAgent.trader_agent.r.hgetall', return_value=session_data), \
         patch('TraderAgent.trader_agent.r.hset', new_callable=AsyncMock) as mock_hset, \
         patch('TraderAgent.trader_agent.stop_session_for_chat_id', return_value={"status": 200, "message": "Session stopped successfully"}) as mock_stop_session:
        response = client.post("/stop_session/", json=session_data)
        assert response.status_code == 200
        assert response.json() == {"status": 200, "message": "Session stopped successfully"}
        mock_stop_session.assert_called_once_with(session_data["chat_id"])
        mock_redis.assert_called_once_with(session_data["chat_id"])

    # Scenario 3: Internal Server Error
    with patch('TraderAgent.trader_agent.r.hgetall', side_effect=Exception("Internal server error")) as mock_redis:
        response = client.post("/stop_session/", json=session_data)
        assert response.status_code == 200
        assert response.json() == {"status": 500, "message": "Internal server error"}
        mock_redis.assert_called_once_with(session_data["chat_id"])