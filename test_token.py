import asyncio
from jose import jwt
from src.app.core.security import create_access_token, create_refresh_token

async def test_tokens():
    # Test access token
    access_data = {"sub": "testuser"}
    access_token = await create_access_token(access_data)
    access_payload = jwt.decode(access_token, "test_secret_key", 
                               algorithms=["HS256"], 
                               options={"verify_signature": False})
    print("Access Token Payload:", access_payload)
    
    # Test refresh token
    refresh_data = {"sub": "testuser"}
    refresh_token = await create_refresh_token(refresh_data)
    refresh_payload = jwt.decode(refresh_token, "test_secret_key", 
                                algorithms=["HS256"], 
                                options={"verify_signature": False})
    print("Refresh Token Payload:", refresh_payload)

if __name__ == "__main__":
    asyncio.run(test_tokens())