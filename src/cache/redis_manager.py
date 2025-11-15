"""
Redis cache manager with multi-level caching strategy

Provides three-level caching:
1. Document classification cache (1 hour TTL)
2. Fact extraction cache (1 hour TTL)
3. Complete result cache (30 min TTL)
4. Learning patterns cache (persistent)

Design: From Phase 1 planning, Section 1.4
Source inspiration: v2 API caching approach
"""

import redis.asyncio as redis
import pickle
import hashlib
import logging
from typing import Optional, Any, List
from datetime import timedelta
import json

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """
    Multi-level Redis caching for performance optimization

    Cache Levels:
    1. doc_class:{hash}  - Document classification (1h TTL)
    2. facts:{hash}      - Extracted facts (1h TTL)
    3. result:{hash}     - Complete processing result (30min TTL)
    4. learning_patterns - Persistent learning patterns (no TTL)

    Performance Impact:
    - Document classification: ~50-100ms saved
    - Fact extraction: ~500-1000ms saved
    - Complete result: ~5-10s saved
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize Redis cache manager

        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379)
        """
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self.connected = False

        # Cache TTLs in seconds
        self.TTL_DOCUMENT_CLASS = 3600  # 1 hour
        self.TTL_FACTS = 3600  # 1 hour
        self.TTL_RESULT = 1800  # 30 minutes
        self.TTL_LEARNING = None  # Persistent (no expiry)

        # Performance tracking
        self.cache_hits = 0
        self.cache_misses = 0

    async def connect(self):
        """
        Initialize Redis connection

        Attempts to connect to Redis. If connection fails, logs warning
        and continues without caching (graceful degradation).
        """
        try:
            self.client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle encoding with pickle
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            await self.client.ping()
            self.connected = True
            logger.info(f"✅ Redis cache connected: {self.redis_url}")
        except Exception as e:
            logger.warning(f"⚠️  Redis connection failed: {e}. Running without cache.")
            self.client = None
            self.connected = False

    async def close(self):
        """Close Redis connection gracefully"""
        if self.client:
            await self.client.close()
            self.connected = False
            logger.info("Redis connection closed")

    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self.connected

    # ========================================================================
    # LEVEL 1: DOCUMENT CLASSIFICATION CACHE
    # ========================================================================

    async def get_document_classification(self, doc_hash: str) -> Optional[Any]:
        """
        Get cached document classification

        Args:
            doc_hash: MD5 hash of document content

        Returns:
            Cached classification or None if not found
        """
        if not self.client:
            return None

        try:
            key = f"doc_class:{doc_hash}"
            cached = await self.client.get(key)

            if cached:
                self.cache_hits += 1
                logger.debug(f"Cache HIT: document classification {doc_hash[:8]}")
                return pickle.loads(cached)
            else:
                self.cache_misses += 1
                logger.debug(f"Cache MISS: document classification {doc_hash[:8]}")
                return None

        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None

    async def set_document_classification(
        self,
        doc_hash: str,
        classification: Any,
        ttl: Optional[int] = None
    ):
        """
        Cache document classification

        Args:
            doc_hash: MD5 hash of document content
            classification: Classification result to cache
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        if not self.client:
            return

        try:
            key = f"doc_class:{doc_hash}"
            ttl = ttl or self.TTL_DOCUMENT_CLASS

            await self.client.set(
                key,
                pickle.dumps(classification),
                ex=ttl
            )
            logger.debug(f"Cached document classification {doc_hash[:8]} (TTL: {ttl}s)")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    # ========================================================================
    # LEVEL 2: FACT EXTRACTION CACHE
    # ========================================================================

    async def get_extracted_facts(self, doc_hash: str) -> Optional[List]:
        """
        Get cached extracted facts

        Args:
            doc_hash: MD5 hash of document content

        Returns:
            List of extracted facts or None if not found
        """
        if not self.client:
            return None

        try:
            key = f"facts:{doc_hash}"
            cached = await self.client.get(key)

            if cached:
                self.cache_hits += 1
                logger.debug(f"Cache HIT: extracted facts {doc_hash[:8]}")
                return pickle.loads(cached)
            else:
                self.cache_misses += 1
                logger.debug(f"Cache MISS: extracted facts {doc_hash[:8]}")
                return None

        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None

    async def set_extracted_facts(
        self,
        doc_hash: str,
        facts: List,
        ttl: Optional[int] = None
    ):
        """
        Cache extracted facts

        Args:
            doc_hash: MD5 hash of document content
            facts: List of extracted facts to cache
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        if not self.client:
            return

        try:
            key = f"facts:{doc_hash}"
            ttl = ttl or self.TTL_FACTS

            await self.client.set(
                key,
                pickle.dumps(facts),
                ex=ttl
            )
            logger.debug(f"Cached extracted facts {doc_hash[:8]} (TTL: {ttl}s, count: {len(facts)})")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    # ========================================================================
    # LEVEL 3: COMPLETE RESULT CACHE
    # ========================================================================

    async def get_complete_result(self, result_hash: str) -> Optional[dict]:
        """
        Get cached complete processing result

        Args:
            result_hash: Hash of input documents (for cache key)

        Returns:
            Complete processing result dict or None if not found
        """
        if not self.client:
            return None

        try:
            key = f"result:{result_hash}"
            cached = await self.client.get(key)

            if cached:
                self.cache_hits += 1
                logger.info(f"🚀 Cache HIT: complete result {result_hash[:8]} (major performance boost!)")
                return pickle.loads(cached)
            else:
                self.cache_misses += 1
                logger.debug(f"Cache MISS: complete result {result_hash[:8]}")
                return None

        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None

    async def set_complete_result(
        self,
        result_hash: str,
        result: dict,
        ttl: Optional[int] = None
    ):
        """
        Cache complete processing result

        Args:
            result_hash: Hash of input documents (for cache key)
            result: Complete processing result to cache
            ttl: Time-to-live in seconds (default: 30 minutes)
        """
        if not self.client:
            return

        try:
            key = f"result:{result_hash}"
            ttl = ttl or self.TTL_RESULT

            await self.client.set(
                key,
                pickle.dumps(result),
                ex=ttl
            )
            logger.debug(f"Cached complete result {result_hash[:8]} (TTL: {ttl}s)")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    # ========================================================================
    # LEVEL 4: LEARNING PATTERNS CACHE (PERSISTENT)
    # ========================================================================

    async def get_learning_patterns(self) -> Optional[dict]:
        """
        Get persisted learning patterns

        Returns:
            Dictionary of learning patterns or None if not found
        """
        if not self.client:
            return None

        try:
            key = "learning_patterns"
            cached = await self.client.get(key)

            if cached:
                logger.debug("Retrieved learning patterns from cache")
                return pickle.loads(cached)
            else:
                logger.debug("No learning patterns in cache")
                return None

        except Exception as e:
            logger.error(f"Learning pattern retrieval error: {e}")
            return None

    async def save_learning_patterns(self, patterns: dict):
        """
        Persist learning patterns (no expiry)

        Args:
            patterns: Dictionary of learning patterns to persist
        """
        if not self.client:
            return

        try:
            key = "learning_patterns"

            await self.client.set(
                key,
                pickle.dumps(patterns),
                ex=None  # Never expire
            )
            logger.info(f"Persisted {len(patterns)} learning patterns to cache")

        except Exception as e:
            logger.error(f"Learning pattern save error: {e}")

    # ========================================================================
    # CACHE INVALIDATION
    # ========================================================================

    async def invalidate_pattern(self, pattern: str):
        """
        Invalidate all keys matching pattern

        Useful when learning patterns are updated and we need to
        invalidate related cached extractions.

        Args:
            pattern: Pattern to match (e.g., "facts:*" to invalidate all fact caches)
        """
        if not self.client:
            return

        try:
            deleted_count = 0
            async for key in self.client.scan_iter(f"*{pattern}*"):
                await self.client.delete(key)
                deleted_count += 1

            logger.info(f"Invalidated {deleted_count} cache entries matching pattern: {pattern}")

        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")

    async def invalidate_all(self):
        """
        Invalidate ALL cache entries (use with caution!)

        Clears the entire cache. Useful for development/testing.
        """
        if not self.client:
            return

        try:
            await self.client.flushdb()
            logger.warning("⚠️  Invalidated ALL cache entries")

        except Exception as e:
            logger.error(f"Cache flush error: {e}")

    # ========================================================================
    # CACHE STATISTICS
    # ========================================================================

    def get_cache_stats(self) -> dict:
        """
        Get cache performance statistics

        Returns:
            Dictionary with cache hit/miss counts and rates
        """
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0.0

        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': round(hit_rate, 2),
            'connected': self.connected
        }

    def reset_cache_stats(self):
        """Reset cache statistics counters"""
        self.cache_hits = 0
        self.cache_misses = 0

    async def get_redis_info(self) -> dict:
        """
        Get Redis server information

        Returns:
            Dictionary with Redis server stats or error message
        """
        if not self.client:
            return {'error': 'Not connected'}

        try:
            info = await self.client.info()
            return {
                'redis_version': info.get('redis_version'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0)
            }

        except Exception as e:
            logger.error(f"Error getting Redis info: {e}")
            return {'error': str(e)}

    # ========================================================================
    # UTILITY FUNCTIONS
    # ========================================================================

    @staticmethod
    def generate_doc_hash(content: str) -> str:
        """
        Generate MD5 hash for document content

        Args:
            content: Document content string

        Returns:
            MD5 hash hex string
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_result_hash(documents: List[dict]) -> str:
        """
        Generate hash for complete document set

        Creates a stable hash based on document contents and order.
        Used for caching complete processing results.

        Args:
            documents: List of document dictionaries

        Returns:
            MD5 hash hex string
        """
        # Sort documents by date to ensure stability
        sorted_docs = sorted(documents, key=lambda x: x.get('date', ''))

        # Create concatenated content string
        content_str = ''.join([
            doc.get('content', '') for doc in sorted_docs
        ])

        return hashlib.md5(content_str.encode('utf-8')).hexdigest()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def create_redis_manager(redis_url: str = "redis://localhost:6379") -> RedisCacheManager:
    """
    Create and connect Redis cache manager

    Args:
        redis_url: Redis connection URL

    Returns:
        Connected RedisCacheManager instance
    """
    manager = RedisCacheManager(redis_url)
    await manager.connect()
    return manager
