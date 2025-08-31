import asyncio
from jose import jwt
from src.app.core.security import create_access_token

async def test():
    token = await create_access_token({'sub': 'test'})
    payload = jwt.decode(token, options={'verify_signature': False})
    print('Payload keys:', list(payload.keys()))
    print('Full payload:', payload)

asyncio.run(test())