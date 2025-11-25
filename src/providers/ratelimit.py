# Rate limiting utilities for API providers
import time
import threading
from typing import Optional

from ..core.logger import get_logger

logger = get_logger("provider.ratelimit")


class RateLimiter:
    """
    Thread-safe rate limiter supporting both RPM (Requests Per Minute) 
    and TPM (Tokens Per Minute) constraints.
    
    Usage:
        limiter = RateLimiter(rpm=15, tpm=250000)
        limiter.acquire()  # Wait if needed to respect RPM
        limiter.acquire_tokens(est_tokens=500)  # Wait if TPM would be exceeded
    """
    
    def __init__(self, rpm: int = 30, tpm: Optional[int] = None, rpd: Optional[int] = None):
        """
        Initialize rate limiter.
        
        Args:
            rpm: Requests per minute limit
            tpm: Tokens per minute limit (optional)
            rpd: Requests per day limit (optional)
        """
        self.rpm = max(1, rpm)
        self.tpm = tpm
        self.rpd = rpd
        self.interval = 60.0 / self.rpm  # seconds between requests
        
        # RPM tracking
        self._lock = threading.Lock()
        self._next_request_time = 0.0
        
        # TPM tracking
        self._token_count = 0
        self._token_window_start = int(time.time() // 60)  # minute window
        
        # RPD tracking
        self._daily_count = 0
        self._daily_window_start = int(time.time() // 86400)  # day window (86400 sec = 24h)
        
        logger.info(f"RateLimiter initialized: RPM={rpm}, TPM={tpm}, RPD={rpd}, interval={self.interval:.2f}s")
    
    def acquire(self):
        """Wait if necessary to respect RPM and RPD limits."""
        with self._lock:
            now = time.time()
            
            # Check RPD limit first (if enabled)
            if self.rpd:
                current_day = int(now // 86400)
                
                # Reset daily window if we're in a new day
                if current_day != self._daily_window_start:
                    self._daily_count = 0
                    self._daily_window_start = current_day
                    logger.debug(f"RPD window reset at day {current_day}")
                
                # Check if we've exceeded daily limit
                if self._daily_count >= self.rpd:
                    logger.error(f"RPD limit exceeded: {self._daily_count}/{self.rpd} requests today")
                    raise RuntimeError(f"Daily quota exceeded: {self._daily_count}/{self.rpd} requests")
                
                # Increment daily counter
                self._daily_count += 1
            
            # Check RPM limit
            if now < self._next_request_time:
                wait_time = self._next_request_time - now
                logger.debug(f"RPM limit: sleeping {wait_time:.2f}s")
                time.sleep(wait_time)
                now = time.time()
            
            self._next_request_time = max(now, self._next_request_time) + self.interval
    
    def acquire_tokens(self, est_tokens: int):
        """
        Wait if necessary to respect TPM limit.
        
        Args:
            est_tokens: Estimated tokens for this request (prompt + max_completion)
        """
        if not self.tpm:
            return
        
        with self._lock:
            now = time.time()
            current_minute = int(now // 60)
            
            # Reset window if we're in a new minute
            if current_minute != self._token_window_start:
                self._token_count = 0
                self._token_window_start = current_minute
                logger.debug(f"TPM window reset at minute {current_minute}")
            
            # Check if adding this request would exceed TPM
            if self._token_count + est_tokens > self.tpm:
                # Wait until next minute window
                sleep_seconds = 60 - (now % 60) + 0.1  # +0.1s buffer
                logger.warning(
                    f"TPM limit would be exceeded "
                    f"({self._token_count + est_tokens} > {self.tpm}); "
                    f"sleeping {sleep_seconds:.1f}s until next window"
                )
                time.sleep(sleep_seconds)
                
                # Reset for new window
                self._token_count = 0
                self._token_window_start = int(time.time() // 60)
            
            self._token_count += est_tokens
            logger.debug(f"TPM: used {self._token_count}/{self.tpm} tokens this minute")
