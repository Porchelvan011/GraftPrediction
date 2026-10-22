import functools
from flask import request, jsonify, g, current_app
import jwt
import datetime
import config


def decode_token(token: str):
    """Decode JWT token using SECRET_KEY. In DEBUG mode allow fallback decoding for migration support."""
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        if config.DEBUG:
            # DEBUG-only fallbacks for development/transition
            fallback_keys = [
                'replace-with-a-random-secret',
                'dev-secret',
                'graftpredict-dev-secret',
            ]
            for fk in fallback_keys:
                try:
                    return jwt.decode(token, fk, algorithms=["HS256"])
                except jwt.InvalidTokenError:
                    continue
        raise


def require_auth(role=None):
    """Decorator to require JWT auth. If role provided, enforces `user` claim matches."""
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return jsonify({"error": "Token missing"}), 401
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return jsonify({"error": "Invalid Authorization header"}), 401
            token = parts[1]
            try:
                decoded = decode_token(token)
            except Exception:
                return jsonify({"error": "Invalid token"}), 401
            # Attach to flask.g
            g.current_user = {
                "user_id": int(decoded.get("user_id")) if decoded.get("user_id") is not None else None,
                "email": decoded.get("email"),
                "user": decoded.get("user")
            }
            if role:
                # allow role to be a string or iterable
                allowed = False
                if isinstance(role, str):
                    allowed = (g.current_user.get("user") or "").lower() == role.lower()
                else:
                    allowed = (g.current_user.get("user") or "").lower() in [r.lower() for r in role]
                if not allowed:
                    return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator
