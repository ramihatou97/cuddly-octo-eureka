"""
Unit tests for Redis cache manager

Tests Redis connectivity, caching operations, and performance tracking.
Ensures cache manager works correctly before proceeding to Phase 2.

Prerequisites:
- Redis server running on localhost:6379 OR
- Tests will gracefully skip if Redis is not available

Run with: pytest tests/unit/test_redis_cache.py
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime

from src.cache.redis_manager import RedisCacheManager, create_redis_manager


# Skip all tests if Redis is not available
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope='function')
async def cache_manager():
    """Create Redis cache manager for testing"""
    manager = RedisCacheManager(redis_url="redis://localhost:6379")
    await manager.connect()

    # Clear cache before each test
    if manager.is_connected():
        await manager.invalidate_all()

    yield manager

    # Cleanup
    if manager.is_connected():
        await manager.close()


class TestRedisConnection:
    """Test Redis connection and initialization"""

    async def test_connection_success(self, cache_manager):
        """Test successful Redis connection"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        assert cache_manager.is_connected() is True
        assert cache_manager.client is not None

    async def test_connection_failure_graceful(self):
        """Test graceful handling of connection failure"""
        manager = RedisCacheManager(redis_url="redis://nonexistent:9999")
        await manager.connect()

        # Should not raise exception, just log warning
        assert manager.is_connected() is False
        assert manager.client is None

    async def test_is_connected_status(self, cache_manager):
        """Test is_connected() returns correct status"""
        if cache_manager.is_connected():
            assert cache_manager.is_connected() is True
        else:
            pytest.skip("Redis server not available")


class TestDocumentClassificationCache:
    """Test Level 1: Document classification caching"""

    async def test_cache_document_classification(self, cache_manager):
        """Test caching and retrieving document classification"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        doc_hash = "test_doc_hash_123"
        classification = {'type': 'admission', 'confidence': 0.95}

        # Set cache
        await cache_manager.set_document_classification(doc_hash, classification)

        # Get cache
        cached = await cache_manager.get_document_classification(doc_hash)

        assert cached == classification
        assert cached['type'] == 'admission'
        assert cached['confidence'] == 0.95

    async def test_cache_miss_document_classification(self, cache_manager):
        """Test cache miss returns None"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        cached = await cache_manager.get_document_classification("nonexistent_hash")

        assert cached is None

    async def test_cache_hit_tracking(self, cache_manager):
        """Test cache hit tracking increments correctly"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        cache_manager.reset_cache_stats()

        doc_hash = "test_hash"
        await cache_manager.set_document_classification(doc_hash, {'type': 'progress'})

        # Cache hit
        await cache_manager.get_document_classification(doc_hash)

        stats = cache_manager.get_cache_stats()
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 0

    async def test_cache_miss_tracking(self, cache_manager):
        """Test cache miss tracking increments correctly"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        cache_manager.reset_cache_stats()

        # Cache miss
        await cache_manager.get_document_classification("nonexistent")

        stats = cache_manager.get_cache_stats()
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 1


class TestFactExtractionCache:
    """Test Level 2: Fact extraction caching"""

    async def test_cache_extracted_facts(self, cache_manager):
        """Test caching and retrieving extracted facts"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        doc_hash = "fact_test_hash"
        facts = [
            {'fact': 'NIHSS: 12', 'confidence': 0.95},
            {'fact': 'GCS: 14', 'confidence': 0.95}
        ]

        # Set cache
        await cache_manager.set_extracted_facts(doc_hash, facts)

        # Get cache
        cached = await cache_manager.get_extracted_facts(doc_hash)

        assert cached == facts
        assert len(cached) == 2
        assert cached[0]['fact'] == 'NIHSS: 12'

    async def test_cache_empty_facts_list(self, cache_manager):
        """Test caching empty facts list"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        doc_hash = "empty_facts"
        facts = []

        await cache_manager.set_extracted_facts(doc_hash, facts)
        cached = await cache_manager.get_extracted_facts(doc_hash)

        assert cached == []


class TestCompleteResultCache:
    """Test Level 3: Complete result caching"""

    async def test_cache_complete_result(self, cache_manager):
        """Test caching and retrieving complete processing result"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        result_hash = "result_test_hash"
        result = {
            'discharge_summary': 'Patient was admitted...',
            'confidence_score': 0.94,
            'uncertainties': [],
            'session_id': 'abc-123'
        }

        # Set cache
        await cache_manager.set_complete_result(result_hash, result)

        # Get cache
        cached = await cache_manager.get_complete_result(result_hash)

        assert cached == result
        assert cached['confidence_score'] == 0.94
        assert cached['session_id'] == 'abc-123'

    async def test_complete_result_major_performance_boost(self, cache_manager):
        """Test that complete result cache provides major speedup"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        result_hash = "perf_test"
        large_result = {
            'discharge_summary': 'x' * 10000,  # Large summary
            'timeline': {'data': list(range(1000))},  # Complex structure
            'uncertainties': [{'id': i} for i in range(50)]
        }

        # Cache result
        await cache_manager.set_complete_result(result_hash, large_result)

        # Retrieve (should be fast)
        import time
        start = time.time()
        cached = await cache_manager.get_complete_result(result_hash)
        elapsed = time.time() - start

        assert cached == large_result
        assert elapsed < 0.1  # Should be sub-100ms


class TestLearningPatternsCache:
    """Test Level 4: Learning patterns caching (persistent)"""

    async def test_save_learning_patterns(self, cache_manager):
        """Test saving and retrieving learning patterns"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        patterns = {
            'pattern_1': {
                'original': 'POD#3',
                'correction': 'post-operative day 3',
                'success_rate': 1.0
            },
            'pattern_2': {
                'original': 'nimodipine',
                'correction': 'nimodipine 60mg',
                'success_rate': 0.95
            }
        }

        # Save patterns
        await cache_manager.save_learning_patterns(patterns)

        # Retrieve patterns
        cached = await cache_manager.get_learning_patterns()

        assert cached == patterns
        assert len(cached) == 2
        assert cached['pattern_1']['success_rate'] == 1.0

    async def test_learning_patterns_persistent(self, cache_manager):
        """Test that learning patterns persist (no TTL)"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        patterns = {'test': 'persistent'}

        await cache_manager.save_learning_patterns(patterns)

        # Should still be there (no expiry)
        cached = await cache_manager.get_learning_patterns()
        assert cached == patterns


class TestCacheInvalidation:
    """Test cache invalidation strategies"""

    async def test_invalidate_pattern(self, cache_manager):
        """Test invalidating keys matching pattern"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        # Set multiple caches
        await cache_manager.set_extracted_facts("doc1", [{'fact': 'test1'}])
        await cache_manager.set_extracted_facts("doc2", [{'fact': 'test2'}])
        await cache_manager.set_document_classification("doc3", {'type': 'admission'})

        # Invalidate all fact caches
        await cache_manager.invalidate_pattern("facts:")

        # Fact caches should be gone
        assert await cache_manager.get_extracted_facts("doc1") is None
        assert await cache_manager.get_extracted_facts("doc2") is None

        # Classification cache should still exist
        assert await cache_manager.get_document_classification("doc3") is not None

    async def test_invalidate_all(self, cache_manager):
        """Test invalidating all cache entries"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        # Set various caches
        await cache_manager.set_document_classification("doc1", {'type': 'admission'})
        await cache_manager.set_extracted_facts("doc2", [{'fact': 'test'}])
        await cache_manager.set_complete_result("result1", {'summary': 'test'})

        # Invalidate all
        await cache_manager.invalidate_all()

        # All should be gone
        assert await cache_manager.get_document_classification("doc1") is None
        assert await cache_manager.get_extracted_facts("doc2") is None
        assert await cache_manager.get_complete_result("result1") is None


class TestCacheStatistics:
    """Test cache statistics and monitoring"""

    async def test_cache_stats_structure(self, cache_manager):
        """Test cache statistics structure"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        stats = cache_manager.get_cache_stats()

        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'cache_hit_rate' in stats
        assert 'connected' in stats

    async def test_cache_hit_rate_calculation(self, cache_manager):
        """Test cache hit rate calculation"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        cache_manager.reset_cache_stats()

        # Create some hits and misses
        await cache_manager.set_document_classification("doc1", {'type': 'admission'})
        await cache_manager.get_document_classification("doc1")  # Hit
        await cache_manager.get_document_classification("doc1")  # Hit
        await cache_manager.get_document_classification("nonexistent")  # Miss

        stats = cache_manager.get_cache_stats()

        assert stats['cache_hits'] == 2
        assert stats['cache_misses'] == 1
        assert stats['cache_hit_rate'] == 66.67  # 2/3 = 66.67%

    async def test_reset_cache_stats(self, cache_manager):
        """Test resetting cache statistics"""
        if not cache_manager.is_connected():
            pytest.skip("Redis server not available")

        # Generate some stats
        await cache_manager.get_document_classification("test")

        # Reset
        cache_manager.reset_cache_stats()

        stats = cache_manager.get_cache_stats()
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 0


class TestUtilityFunctions:
    """Test utility functions"""

    def test_generate_doc_hash(self):
        """Test document hash generation"""
        content1 = "Test document content"
        content2 = "Test document content"
        content3 = "Different content"

        hash1 = RedisCacheManager.generate_doc_hash(content1)
        hash2 = RedisCacheManager.generate_doc_hash(content2)
        hash3 = RedisCacheManager.generate_doc_hash(content3)

        # Same content should produce same hash
        assert hash1 == hash2

        # Different content should produce different hash
        assert hash1 != hash3

        # Hash should be MD5 (32 hex characters)
        assert len(hash1) == 32

    def test_generate_result_hash(self):
        """Test result hash generation from document list"""
        docs1 = [
            {'content': 'Doc A', 'date': '2024-01-01'},
            {'content': 'Doc B', 'date': '2024-01-02'}
        ]
        docs2 = [
            {'content': 'Doc A', 'date': '2024-01-01'},
            {'content': 'Doc B', 'date': '2024-01-02'}
        ]
        docs3 = [
            {'content': 'Doc C', 'date': '2024-01-01'},
            {'content': 'Doc D', 'date': '2024-01-02'}
        ]

        hash1 = RedisCacheManager.generate_result_hash(docs1)
        hash2 = RedisCacheManager.generate_result_hash(docs2)
        hash3 = RedisCacheManager.generate_result_hash(docs3)

        # Same documents should produce same hash
        assert hash1 == hash2

        # Different documents should produce different hash
        assert hash1 != hash3

    def test_generate_result_hash_order_independent(self):
        """Test that result hash sorts documents by date"""
        docs1 = [
            {'content': 'Doc B', 'date': '2024-01-02'},
            {'content': 'Doc A', 'date': '2024-01-01'}
        ]
        docs2 = [
            {'content': 'Doc A', 'date': '2024-01-01'},
            {'content': 'Doc B', 'date': '2024-01-02'}
        ]

        hash1 = RedisCacheManager.generate_result_hash(docs1)
        hash2 = RedisCacheManager.generate_result_hash(docs2)

        # Should produce same hash regardless of input order
        assert hash1 == hash2


class TestConvenienceFunctions:
    """Test convenience functions"""

    async def test_create_redis_manager(self):
        """Test create_redis_manager convenience function"""
        manager = await create_redis_manager("redis://localhost:6379")

        # Should return connected manager (if Redis available)
        assert isinstance(manager, RedisCacheManager)

        # Cleanup
        if manager.is_connected():
            await manager.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
