# import logging
# import os
# from typing import Annotated

# import jwt
# from fastapi import HTTPException, Request
# from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# from pydantic import BaseModel
# from typing_extensions import Doc


# logger = logging.getLogger(__name__)


# class TelegramData(BaseModel):
#     """Model for Telegram authentication data"""

#     id: int
#     first_name: str
#     username: str | None
#     photo_url: str | None
#     auth_date: int
#     hash: str


# class JWTBearer(HTTPBearer):
#     def __init__(self, *, auto_error: bool = True) -> None:
#         super().__init__(auto_error=auto_error)
#         self.jwt_secrete_key = self._load_jwt_secret_key()

#     def _load_jwt_secret_key(self) -> str:
#         jwt_secret_key = os.getenv("JWT_SECRET_KEY")
#         if not jwt_secret_key:
#             raise ValueError("JWT_SECRET_KEY environment variable not found.")
#         return jwt_secret_key

#     async def __call__(self, request: Request) -> Annotated[str, Doc]:
#         """
#         Handle the incoming request and performs JWT authentication.

#         Args:
#             request (Request): The incoming HTTP request.

#         Returns:
#             str: The JWT token if authentication is successful.

#         Raises:
#             HTTPException: If the authorization code is invalid, the authentication scheme is not "Bearer",
#                            or the token is invalid or expired.
#         """
#         credentials: HTTPAuthorizationCredentials = await super().__call__(request)
#         if not credentials:
#             raise HTTPException(status_code=403, detail="Invalid authorization code.")
#         if credentials.scheme != "Bearer":
#             raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
#         if not self.verify_jwt(credentials.credentials):
#             raise HTTPException(status_code=403, detail="Invalid token or expired token.")
#         return credentials.credentials

#     def verify_jwt(self, jwt_token: str) -> bool:
#         """Verify JWT token"""
#         try:
#             payload = jwt.decode(jwt_token, self.jwt_secret_key, algorithms=["HS256"])
#         except jwt.PyJWTError:
#             logger.exception("JWT verification failed")
#             return False
#         return bool(payload)
