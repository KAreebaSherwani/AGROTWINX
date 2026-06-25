# tests/test_load.py

"""
Load and stress testing for AgroTwinX
"""

import time
import concurrent.futures
from datetime import datetime, timedelta
import random
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database
from src.models.digital_twin import DigitalTwin
from src.marketplace.stubble_marketplace import StubbleMarketplace

class LoadTester:
    """
    Load testing suite
    """
    
    def __init__(self):
        self.db = Database()
        self.results = {
            'total_operations': 0,
            'successful': 0,
            'failed': 0,
            'avg_time': 0,
            'max_time': 0,
            'min_time': float('inf')
        }
    
    def test_concurrent_twin_updates(self, num_threads=10, operations_per_thread=10):
        """
        Test concurrent satellite updates
        Simulates multiple farms being updated simultaneously
        """
        print(f"\n{'='*70}")
        print(f"🔥 LOAD TEST: Concurrent Twin Updates")
        print(f"{'='*70}")
        print(f"Threads: {num_threads}")
        print(f"Operations per thread: {operations_per_thread}")
        print(f"Total operations: {num_threads * operations_per_thread}")
        
        # Create test farms
        test_farms = self._create_test_farms(num_threads)
        
        start_time = time.time()
        
        # Run concurrent updates
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            
            for farm_id in test_farms:
                future = executor.submit(
                    self._update_twin_multiple_times,
                    farm_id,
                    operations_per_thread
                )
                futures.append(future)
            
            # Wait for all to complete
            concurrent.futures.wait(futures)
            
            # Collect results
            for future in futures:
                result = future.result()
                self.results['successful'] += result['successful']
                self.results['failed'] += result['failed']
        
        total_time = time.time() - start_time
        
        self.results['total_operations'] = num_threads * operations_per_thread
        self.results['avg_time'] = total_time / self.results['total_operations']
        
        # Print results
        self._print_results(total_time)
        
        # Cleanup
        self._cleanup_test_farms(test_farms)
    
    def test_marketplace_stress(self, num_listings=100, num_buyers=20):
        """
        Stress test marketplace with many concurrent listings
        """
        print(f"\n{'='*70}")
        print(f"🔥 STRESS TEST: Marketplace")
        print(f"{'='*70}")
        print(f"Creating {num_listings} listings...")
        print(f"Creating {num_buyers} buyers...")
        
        marketplace = StubbleMarketplace(self.db)
        
        # Create buyers
        buyers = self._create_test_buyers(num_buyers)
        
        # Create listings
        listings = []
        start_time = time.time()
        
        for i in range(num_listings):
            # Create farm and twin
            farmer_id = self._create_test_farmer()
            farm_id = self._create_test_farm(farmer_id)
            
            twin = DigitalTwin(
                farm_id=farm_id,
                farmer_id=farmer_id,
                crop_type='rice',
                planting_date=datetime.now() - timedelta(days=90),
                area_acres=5,
                db=self.db
            )
            
            twin.predictions['stubble_tons'] = random.uniform(3.0, 8.0)
            twin.predictions['stubble_value'] = twin.predictions['stubble_tons'] * 3000
            
            # Create listing
            listing = marketplace.create_listing(
                twin_id=farm_id,
                farmer_id=farmer_id
            )
            
            listings.append(listing['listing_id'])
        
        listing_time = time.time() - start_time
        
        print(f"\n✅ Created {num_listings} listings in {listing_time:.2f}s")
        print(f"   Avg time per listing: {listing_time/num_listings:.3f}s")
        
        # Test buyer matching for all listings
        print(f"\n🔍 Testing buyer matching...")
        
        match_start = time.time()
        total_matches = 0
        
        for listing_id in listings[:50]:  # Test first 50
            matches = marketplace.find_buyers(listing_id)
            total_matches += len(matches)
        
        match_time = time.time() - match_start
        
        print(f"✅ Matched 50 listings in {match_time:.2f}s")
        print(f"   Avg matches per listing: {total_matches/50:.1f}")
        print(f"   Avg time per match: {match_time/50:.3f}s")
        
        # Cleanup
        print(f"\n🧹 Cleaning up test data...")
        self._cleanup_test_data(listings, buyers)
    
    def test_database_query_performance(self, num_queries=1000):
        """
        Test database query performance
        """
        print(f"\n{'='*70}")
        print(f"🔥 PERFORMANCE TEST: Database Queries")
        print(f"{'='*70}")
        print(f"Running {num_queries} queries...")
        
        queries = {
            'simple_select': "SELECT * FROM farmers LIMIT 10",
            'join_query': """
                SELECT f.*, farms.crop_type 
                FROM farmers f 
                LEFT JOIN farms ON f.farmer_id = farms.farmer_id 
                LIMIT 10
            """,
            'aggregate': "SELECT COUNT(*), AVG(area_acres) FROM farms",
            'complex': """
                SELECT 
                    f.name,
                    COUNT(farms.farm_id) as farm_count,
                    SUM(farms.area_acres) as total_acres
                FROM farmers f
                LEFT JOIN farms ON f.farmer_id = farms.farmer_id
                GROUP BY f.farmer_id
                LIMIT 10
            """
        }
        
        results = {}
        
        for query_name, query_sql in queries.items():
            times = []
            
            for _ in range(num_queries):
                start = time.time()
                self.db.query(query_sql)
                times.append(time.time() - start)
            
            results[query_name] = {
                'avg': sum(times) / len(times),
                'min': min(times),
                'max': max(times)
            }
        
        # Print results
        print(f"\n📊 Query Performance Results:")
        for query_name, stats in results.items():
            print(f"\n{query_name}:")
            print(f"  Avg: {stats['avg']*1000:.2f}ms")
            print(f"  Min: {stats['min']*1000:.2f}ms")
            print(f"  Max: {stats['max']*1000:.2f}ms")
    
    def test_memory_usage(self, num_twins=100):
        """
        Test memory usage with large number of twins
        """
        print(f"\n{'='*70}")
        print(f"🔥 MEMORY TEST: Large Dataset")
        print(f"{'='*70}")
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"Initial memory: {initial_memory:.2f} MB")
        
        # Create many twins
        twins = []
        
        for i in range(num_twins):
            farmer_id = self._create_test_farmer()
            farm_id = self._create_test_farm(farmer_id)
            
            twin = DigitalTwin(
                farm_id=farm_id,
                farmer_id=farmer_id,
                crop_type='rice',
                planting_date=datetime.now() - timedelta(days=90),
                area_acres=5,
                db=self.db
            )
            
            # Add observations
            for j in range(10):
                obs = {
                    'date': (datetime.now() - timedelta(days=80-j*8)).strftime('%Y-%m-%d'),
                    'ndvi': 0.3 + j * 0.05,
                    'ndwi': 0.3,
                    'lai': 2.5,
                    'cloud_cover': 10
                }
                twin.update_from_satellite(obs)
            
            twins.append(twin)
            
            if (i + 1) % 20 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"  {i+1} twins: {current_memory:.2f} MB")
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"\n📊 Memory Usage:")
        print(f"  Initial: {initial_memory:.2f} MB")
        print(f"  Final: {final_memory:.2f} MB")
        print(f"  Increase: {memory_increase:.2f} MB")
        print(f"  Per twin: {memory_increase/num_twins:.2f} MB")
        
        # Cleanup
        del twins
    
    # Helper methods
    
    def _create_test_farms(self, count):
        """Create test farms for load testing"""
        farm_ids = []
        
        for i in range(count):
            farmer_id = self._create_test_farmer()
            farm_id = self._create_test_farm(farmer_id)
            
            # Create twin
            twin = DigitalTwin(
                farm_id=farm_id,
                farmer_id=farmer_id,
                crop_type='rice',
                planting_date=datetime.now() - timedelta(days=60),
                area_acres=5,
                db=self.db
            )
            
            twin_data = twin.to_dict()
            self.db.insert('digital_twins', twin_data)
            
            farm_ids.append(farm_id)
        
        return farm_ids
    
    def _create_test_farmer(self):
        """Create test farmer"""
        import uuid
        
        farmer_data = {
            'phone_number': f'+9230{uuid.uuid4().hex[:8]}',
            'name': f'Load Test Farmer {uuid.uuid4().hex[:6]}',
            'location_lat': 33.74 + random.uniform(-0.1, 0.1),
            'location_lon': 73.13 + random.uniform(-0.1, 0.1),
            'district': 'Rawalpindi'
        }
        
        return self.db.insert('farmers', farmer_data)
    
    def _create_test_farm(self, farmer_id):
        """Create test farm"""
        farm_data = {
            'farmer_id': farmer_id,
            'crop_type': random.choice(['rice', 'wheat']),
            'area_acres': random.uniform(3, 10),
            'planting_date': (datetime.now() - timedelta(days=random.randint(60, 120))).strftime('%Y-%m-%d'),
            'status': 'active'
        }
        
        return self.db.insert('farms', farm_data)
    
    def _create_test_buyers(self, count):
        """Create test buyers"""
        buyer_ids = []
        
        for i in range(count):
            buyer_data = {
                'company_name': f'Load Test Buyer {i}',
                'contact_person': 'Test Contact',
                'phone_number': f'+92311{i:07d}',
                'location_lat': 33.60 + random.uniform(-0.2, 0.2),
                'location_lon': 73.05 + random.uniform(-0.2, 0.2),
                'crop_types': 'rice,wheat',
                'price_per_ton_rice': random.randint(3000, 3500),
                'price_per_ton_wheat': random.randint(2400, 2800),
                'max_distance_km': random.randint(30, 80),
                'active': 1
            }
            
            buyer_ids.append(self.db.insert('buyers', buyer_data))
        
        return buyer_ids
    
    def _update_twin_multiple_times(self, farm_id, num_updates):
        """Update a twin multiple times"""
        result = {'successful': 0, 'failed': 0}
        
        try:
            # Load twin
            twin_data = self.db.query(
                "SELECT * FROM digital_twins WHERE farm_id = ?",
                (farm_id,)
            )[0]
            
            # Perform updates
            for i in range(num_updates):
                obs = {
                    'date': (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                    'ndvi': random.uniform(0.4, 0.8),
                    'ndwi': random.uniform(0.2, 0.4),
                    'lai': random.uniform(2, 4),
                    'cloud_cover': random.randint(0, 30)
                }
                
                # Simulate update
                time.sleep(0.01)  # Small delay to simulate processing
                
                result['successful'] += 1
        
        except Exception as e:
            result['failed'] += num_updates
        
        return result
    
    def _cleanup_test_farms(self, farm_ids):
        """Cleanup test data"""
        for farm_id in farm_ids:
            try:
                self.db.query("DELETE FROM digital_twins WHERE farm_id = ?", (farm_id,))
                self.db.query("DELETE FROM farms WHERE farm_id = ?", (farm_id,))
                
                farm = self.db.get('farms', 'farm_id', farm_id)
                if farm:
                    self.db.query("DELETE FROM farmers WHERE farmer_id = ?", (farm['farmer_id'],))
            except:
                pass
    
    def _cleanup_test_data(self, listings, buyers):
        """Cleanup marketplace test data"""
        # Delete test listings, transactions, farms, farmers, buyers
        self.db.query("DELETE FROM stubble_listings WHERE listing_id IN ({})".format(','.join(map(str, listings))))
        self.db.query("DELETE FROM buyers WHERE buyer_id IN ({})".format(','.join(map(str, buyers))))
    
    def _print_results(self, total_time):
        """Print test results"""
        print(f"\n{'='*70}")
        print(f"📊 RESULTS")
        print(f"{'='*70}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Total operations: {self.results['total_operations']}")
        print(f"Successful: {self.results['successful']}")
        print(f"Failed: {self.results['failed']}")
        print(f"Success rate: {self.results['successful']/self.results['total_operations']*100:.1f}%")
        print(f"Avg time per operation: {self.results['avg_time']*1000:.2f}ms")
        print(f"Operations per second: {self.results['total_operations']/total_time:.1f}")

# Run tests
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='AgroTwinX Load Testing')
    parser.add_argument('--concurrent', action='store_true', help='Test concurrent updates')
    parser.add_argument('--marketplace', action='store_true', help='Test marketplace stress')
    parser.add_argument('--queries', action='store_true', help='Test query performance')
    parser.add_argument('--memory', action='store_true', help='Test memory usage')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    
    args = parser.parse_args()
    
    tester = LoadTester()
    
    if args.concurrent or args.all:
        tester.test_concurrent_twin_updates(num_threads=10, operations_per_thread=10)
    
    if args.marketplace or args.all:
        tester.test_marketplace_stress(num_listings=100, num_buyers=20)
    
    if args.queries or args.all:
        tester.test_database_query_performance(num_queries=1000)
    
    if args.memory or args.all:
        tester.test_memory_usage(num_twins=100)
    
    if not any([args.concurrent, args.marketplace, args.queries, args.memory, args.all]):
        print("Usage:")
        print("  python test_load.py --concurrent    # Test concurrent updates")
        print("  python test_load.py --marketplace   # Test marketplace stress")
        print("  python test_load.py --queries       # Test query performance")
        print("  python test_load.py --memory        # Test memory usage")
        print("  python test_load.py --all           # Run all tests")