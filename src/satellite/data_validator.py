# src/satellite/data_validator.py

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database

class SatelliteDataValidator:
    """
    Validate satellite data quality and flag anomalies
    Ensures data integrity before updating digital twins
    """
    
    def __init__(self):
        self.db = Database()
        
        # Validation thresholds
        self.ndvi_range = (-0.2, 1.0)  # Valid NDVI range
        self.ndwi_range = (-1.0, 1.0)  # Valid NDWI range
        self.lai_range = (0, 10)       # Valid LAI range
        self.cloud_threshold = 30      # Max acceptable cloud cover (%)
        
        print("✅ Data Validator initialized")
    
    def validate_observation(self, observation):
        """
        Validate a single satellite observation
        
        Returns:
            dict: {
                'valid': bool,
                'issues': list of issues found,
                'quality_score': 0-100
            }
        """
        issues = []
        quality_score = 100
        
        # 1. Check NDVI
        if observation.get('ndvi') is not None:
            ndvi = observation['ndvi']
            
            if not (self.ndvi_range[0] <= ndvi <= self.ndvi_range[1]):
                issues.append(f"NDVI out of range: {ndvi}")
                quality_score -= 20
            
            # Check for extreme values
            if ndvi < 0.1 and observation.get('date'):
                # Very low NDVI might indicate bare soil or water
                days_since_planting = self._calculate_days_since_planting(observation.get('farm_id'))
                
                if days_since_planting and days_since_planting > 30:
                    issues.append(f"Unusually low NDVI ({ndvi}) for crop age")
                    quality_score -= 15
        else:
            issues.append("Missing NDVI value")
            quality_score -= 30
        
        # 2. Check NDWI
        if observation.get('ndwi') is not None:
            ndwi = observation['ndwi']
            
            if not (self.ndwi_range[0] <= ndwi <= self.ndwi_range[1]):
                issues.append(f"NDWI out of range: {ndwi}")
                quality_score -= 10
        
        # 3. Check LAI
        if observation.get('lai') is not None:
            lai = observation['lai']
            
            if not (self.lai_range[0] <= lai <= self.lai_range[1]):
                issues.append(f"LAI out of range: {lai}")
                quality_score -= 10
        
        # 4. Check cloud cover
        if observation.get('cloud_cover') is not None:
            cloud_cover = observation['cloud_cover']
            
            if cloud_cover > self.cloud_threshold:
                issues.append(f"High cloud cover: {cloud_cover}%")
                quality_score -= (cloud_cover - self.cloud_threshold)
        else:
            issues.append("Missing cloud cover data")
            quality_score -= 5
        
        # 5. Check date validity
        if observation.get('date'):
            try:
                obs_date = datetime.strptime(observation['date'], '%Y-%m-%d')
                
                if obs_date > datetime.now():
                    issues.append("Future date")
                    quality_score -= 50
                
                if obs_date < datetime.now() - timedelta(days=365):
                    issues.append("Very old data")
                    quality_score -= 10
            except:
                issues.append("Invalid date format")
                quality_score -= 20
        
        # 6. Check for missing critical data
        required_fields = ['date', 'ndvi']
        for field in required_fields:
            if field not in observation or observation[field] is None:
                issues.append(f"Missing required field: {field}")
                quality_score -= 25
        
        quality_score = max(0, quality_score)
        
        return {
            'valid': quality_score >= 50,  # Must score 50+ to be valid
            'issues': issues,
            'quality_score': quality_score
        }
    
    def validate_ndvi_trend(self, farm_id):
        """
        Validate NDVI trend for logical consistency
        Crops should generally increase then decrease
        """
        # Get observation history
        twin_data = self.db.query(
            "SELECT * FROM digital_twins WHERE farm_id = ?",
            (farm_id,)
        )
        
        if not twin_data:
            return {'valid': True, 'issues': []}
        
        history = json.loads(twin_data[0].get('satellite_history', '[]'))
        
        if len(history) < 3:
            return {'valid': True, 'issues': []}  # Not enough data
        
        issues = []
        
        # Get NDVI values
        ndvi_values = [obs['ndvi'] for obs in history if obs.get('ndvi')]
        
        if len(ndvi_values) < 3:
            return {'valid': True, 'issues': []}
        
        # Check for impossible jumps
        for i in range(1, len(ndvi_values)):
            diff = abs(ndvi_values[i] - ndvi_values[i-1])
            
            # NDVI shouldn't change by more than 0.3 between observations
            if diff > 0.3:
                issues.append(f"Large NDVI jump: {ndvi_values[i-1]:.2f} → {ndvi_values[i]:.2f}")
        
        # Check overall trend
        # Early stage: should increase
        early_values = ndvi_values[:len(ndvi_values)//2]
        if early_values:
            if early_values[-1] < early_values[0] - 0.1:
                issues.append("NDVI declining in early growth stage")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    def _calculate_days_since_planting(self, farm_id):
        """Calculate days since planting for a farm"""
        if not farm_id:
            return None
        
        farm = self.db.get('farms', 'farm_id', farm_id)
        if not farm:
            return None
        
        planting_date = datetime.strptime(farm['planting_date'], '%Y-%m-%d')
        return (datetime.now() - planting_date).days
    
    def validate_all_twins(self):
        """
        Run validation on all digital twins
        Generate report of data quality issues
        """
        print(f"\n{'='*70}")
        print(f"🔍 DATA VALIDATION REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        twins = self.db.query("SELECT * FROM digital_twins")
        
        report = {
            'total_twins': len(twins),
            'valid_twins': 0,
            'invalid_twins': 0,
            'issues_found': [],
            'avg_quality_score': 0
        }
        
        quality_scores = []
        
        for twin_data in twins:
            farm_id = twin_data['farm_id']
            history = json.loads(twin_data.get('satellite_history', '[]'))
            
            print(f"\n📊 Farm #{farm_id}:")
            
            if not history:
                print("  ⚠️  No observation history")
                report['issues_found'].append(f"Farm {farm_id}: No data")
                continue
            
            # Validate latest observation
            latest = history[-1] if history else None
            
            if latest:
                validation = self.validate_observation(latest)
                quality_scores.append(validation['quality_score'])
                
                print(f"  Quality Score: {validation['quality_score']}/100")
                
                if validation['valid']:
                    print(f"  ✅ Valid")
                    report['valid_twins'] += 1
                else:
                    print(f"  ❌ Invalid")
                    report['invalid_twins'] += 1
                
                if validation['issues']:
                    print(f"  Issues:")
                    for issue in validation['issues']:
                        print(f"    - {issue}")
                    
                    report['issues_found'].append({
                        'farm_id': farm_id,
                        'issues': validation['issues']
                    })
            
            # Validate NDVI trend
            trend_validation = self.validate_ndvi_trend(farm_id)
            
            if not trend_validation['valid']:
                print(f"  ⚠️  Trend issues:")
                for issue in trend_validation['issues']:
                    print(f"    - {issue}")
        
        # Calculate average quality
        if quality_scores:
            report['avg_quality_score'] = sum(quality_scores) / len(quality_scores)
        
        # Print summary
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"Total twins: {report['total_twins']}")
        print(f"Valid: {report['valid_twins']} ({report['valid_twins']/max(report['total_twins'],1)*100:.1f}%)")
        print(f"Invalid: {report['invalid_twins']}")
        print(f"Avg Quality Score: {report['avg_quality_score']:.1f}/100")
        print(f"Total Issues: {len(report['issues_found'])}")
        
        return report
    
    def auto_fix_issues(self, farm_id):
        """
        Attempt to automatically fix common data issues
        """
        print(f"\n🔧 Auto-fixing issues for farm #{farm_id}...")
        
        twin_data = self.db.query(
            "SELECT * FROM digital_twins WHERE farm_id = ?",
            (farm_id,)
        )
        
        if not twin_data:
            print("  ❌ Twin not found")
            return False
        
        history = json.loads(twin_data[0].get('satellite_history', '[]'))
        
        if not history:
            print("  ❌ No data to fix")
            return False
        
        fixed_count = 0
        
        # Fix 1: Remove observations with cloud cover > 50%
        clean_history = []
        for obs in history:
            if obs.get('cloud_cover', 0) <= 50:
                clean_history.append(obs)
            else:
                fixed_count += 1
        
        # Fix 2: Interpolate missing NDVI values
        for i in range(1, len(clean_history) - 1):
            if clean_history[i].get('ndvi') is None:
                prev_ndvi = clean_history[i-1].get('ndvi')
                next_ndvi = clean_history[i+1].get('ndvi')
                
                if prev_ndvi and next_ndvi:
                    clean_history[i]['ndvi'] = (prev_ndvi + next_ndvi) / 2
                    fixed_count += 1
        
        # Fix 3: Cap extreme values
        for obs in clean_history:
            if obs.get('ndvi'):
                if obs['ndvi'] < -0.2:
                    obs['ndvi'] = -0.2
                    fixed_count += 1
                elif obs['ndvi'] > 1.0:
                    obs['ndvi'] = 1.0
                    fixed_count += 1
        
        # Update database
        if fixed_count > 0:
            self.db.update(
                'digital_twins',
                'farm_id',
                farm_id,
                {'satellite_history': json.dumps(clean_history)}
            )
            
            print(f"  ✅ Fixed {fixed_count} issues")
            return True
        else:
            print("  ℹ️  No issues to fix")
            return False

# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Satellite Data Validator')
    parser.add_argument('--validate-all', action='store_true', help='Validate all twins')
    parser.add_argument('--fix', type=int, help='Auto-fix issues for farm ID')
    
    args = parser.parse_args()
    
    validator = SatelliteDataValidator()
    
    if args.validate_all:
        validator.validate_all_twins()
    
    elif args.fix:
        validator.auto_fix_issues(args.fix)
    
    else:
        print("Usage:")
        print("  python data_validator.py --validate-all    # Validate all twins")
        print("  python data_validator.py --fix 1           # Auto-fix farm 1")