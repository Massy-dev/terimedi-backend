import hashlib

from django.core.cache import cache


class RateLimitExceeded(Exception):
    def __init__(self, retry_after=60):
        self.retry_after = max(1, int(retry_after))
        super().__init__("Too many OTP requests.")


class OTPRateLimiter:
    PHONE_LIMIT = 3
    IP_LIMIT = 10
    WINDOW_SECONDS = 3600
    COOLDOWN_SECONDS = 60

    LUA_SCRIPT = """
    local phone_key = KEYS[1]
    local ip_key = KEYS[2]
    local cooldown_key = KEYS[3]

    local phone_limit = tonumber(ARGV[1])
    local ip_limit = tonumber(ARGV[2])
    local window = tonumber(ARGV[3])
    local cooldown = tonumber(ARGV[4])

    local phone_count = tonumber(redis.call('GET', phone_key) or '0')
    local ip_count = tonumber(redis.call('GET', ip_key) or '0')

    if redis.call('EXISTS', cooldown_key) == 1 then
        return {0, redis.call('TTL', cooldown_key)}
    end

    if phone_count >= phone_limit then
        return {0, redis.call('TTL', phone_key)}
    end

    if ip_count >= ip_limit then
        return {0, redis.call('TTL', ip_key)}
    end

    if redis.call('INCR', phone_key) == 1 then
        redis.call('EXPIRE', phone_key, window)
    end

    if redis.call('INCR', ip_key) == 1 then
        redis.call('EXPIRE', ip_key, window)
    end

    redis.call('SET', cooldown_key, '1', 'EX', cooldown)

    return {1, 0}
    """

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()

    @classmethod
    def check(cls, phone: str, ip_address: str):
        client = cache.client.get_client(write=True)

        phone_hash = cls._hash(phone)
        ip_hash = cls._hash(ip_address)

        keys = [
            f"prelaunch:otp:phone:{phone_hash}",
            f"prelaunch:otp:ip:{ip_hash}",
            f"prelaunch:otp:cooldown:{phone_hash}",
        ]

        result = client.eval(
            cls.LUA_SCRIPT,
            len(keys),
            *keys,
            cls.PHONE_LIMIT,
            cls.IP_LIMIT,
            cls.WINDOW_SECONDS,
            cls.COOLDOWN_SECONDS,
        )

        allowed, retry_after = result

        if not allowed:
            raise RateLimitExceeded(retry_after)

        return True