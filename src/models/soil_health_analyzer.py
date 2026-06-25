# src/models/soil_health_analyzer.py

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import SOIL_TYPES, CROPS

class SoilHealthAnalyzer:
    """
    Soil health assessment and fertilizer recommendations
    Based on:
    - Soil type (from Punjab soil survey)
    - Years of cultivation
    - Crop type
    - NDVI proxy for nutrient status
    """
    
    def __init__(self):
        pass
    
    def assess_soil_health(self, soil_type, years_cultivated, crop_type, current_ndvi=None):
        """
        Assess soil nutrient levels
        
        Args:
            soil_type: 'alluvial', 'loamy', 'sandy', 'clay'
            years_cultivated: How many years field has been farmed
            crop_type: 'rice' or 'wheat'
            current_ndvi: Current NDVI value (optional, for cross-check)
        
        Returns:
            dict: Nutrient assessment
        """
        print(f"\n🌱 Analyzing soil health for {soil_type} soil")
        
        # Get base nutrient levels
        if soil_type not in SOIL_TYPES:
            soil_type = 'loamy'  # Default
        
        base = SOIL_TYPES[soil_type]
        
        # Calculate depletion based on years
        # Nitrogen depletes fastest (10% per year)
        # Phosphorus depletes slower (5% per year)
        # Potassium depletes slowest (3% per year)
        
        nitrogen_depletion = min(80, years_cultivated * 10)  # Max 80% depletion
        phosphorus_depletion = min(60, years_cultivated * 5)
        potassium_depletion = min(50, years_cultivated * 3)
        
        current_nitrogen = base['base_nitrogen'] * (1 - nitrogen_depletion / 100)
        current_phosphorus = base['base_phosphorus'] * (1 - phosphorus_depletion / 100)
        current_potassium = base['base_potassium'] * (1 - potassium_depletion / 100)
        
        # Categorize nutrient levels
        nitrogen_status = self._categorize_nutrient(current_nitrogen, 'nitrogen')
        phosphorus_status = self._categorize_nutrient(current_phosphorus, 'phosphorus')
        potassium_status = self._categorize_nutrient(current_potassium, 'potassium')
        
        # Cross-check with NDVI if available
        if current_ndvi is not None:
            # Low NDVI + adequate nutrients = water/disease issue
            # Low NDVI + low nutrients = fertilizer needed
            if current_ndvi < 0.5 and nitrogen_status != 'deficient':
                ndvi_flag = "Low NDVI despite adequate nutrients - check for disease or water stress"
            else:
                ndvi_flag = "NDVI consistent with nutrient status"
        else:
            ndvi_flag = None
        
        return {
            'soil_type': soil_type,
            'years_cultivated': years_cultivated,
            'nitrogen': {
                'current': round(current_nitrogen, 2),
                'status': nitrogen_status,
                'unit': '% by weight'
            },
            'phosphorus': {
                'current': round(current_phosphorus, 1),
                'status': phosphorus_status,
                'unit': 'ppm'
            },
            'potassium': {
                'current': round(current_potassium, 1),
                'status': potassium_status,
                'unit': 'ppm'
            },
            'ph': base['ph_range'],
            'organic_matter': round(base['organic_matter'] * (1 - years_cultivated * 0.05), 2),
            'ndvi_check': ndvi_flag,
            'overall_health': self._calculate_overall_health(
                nitrogen_status, 
                phosphorus_status, 
                potassium_status
            )
        }
    
    def _categorize_nutrient(self, value, nutrient_type):
        """Categorize nutrient level"""
        thresholds = {
            'nitrogen': {'deficient': 0.5, 'adequate': 1.0, 'high': 1.5},
            'phosphorus': {'deficient': 8, 'adequate': 15, 'high': 25},
            'potassium': {'deficient': 100, 'adequate': 150, 'high': 200}
        }
        
        thresh = thresholds[nutrient_type]
        
        if value < thresh['deficient']:
            return 'deficient'
        elif value < thresh['adequate']:
            return 'low'
        elif value < thresh['high']:
            return 'adequate'
        else:
            return 'high'
    
    def _calculate_overall_health(self, n_status, p_status, k_status):
        """Calculate overall soil health score"""
        scores = {'deficient': 0, 'low': 1, 'adequate': 2, 'high': 3}
        
        total = scores[n_status] + scores[p_status] + scores[k_status]
        max_score = 9
        
        percentage = (total / max_score) * 100
        
        if percentage >= 75:
            return 'excellent'
        elif percentage >= 50:
            return 'good'
        elif percentage >= 25:
            return 'fair'
        else:
            return 'poor'
    
    def recommend_fertilizer(self, assessment, crop_type, area_acres):
        """
        Recommend fertilizer based on assessment
        
        Returns:
            dict: Fertilizer recommendations
        """
        recommendations = []
        total_cost = 0
        
        # Nitrogen (Urea)
        if assessment['nitrogen']['status'] in ['deficient', 'low']:
            # Calculate Urea requirement
            if assessment['nitrogen']['status'] == 'deficient':
                urea_bags_per_acre = 3  # 1 bag = 50kg
            else:
                urea_bags_per_acre = 2
            
            total_bags = urea_bags_per_acre * area_acres
            cost = total_bags * 2500  # Rs. 2500 per bag (50kg)
            
            recommendations.append({
                'nutrient': 'Nitrogen',
                'nutrient_urdu': 'نائٹروجن',
                'fertilizer': 'Urea',
                'fertilizer_urdu': 'یوریا',
                'bags_per_acre': urea_bags_per_acre,
                'total_bags': round(total_bags, 1),
                'bag_weight_kg': 50,
                'cost_per_bag': 2500,
                'total_cost': cost,
                'timing': 'Split application: 50% at planting, 50% at tillering',
                'timing_urdu': 'بوائی میں 50%، کلے نکلنے میں 50%'
            })
            total_cost += cost
        
        # Phosphorus (DAP)
        if assessment['phosphorus']['status'] in ['deficient', 'low']:
            if assessment['phosphorus']['status'] == 'deficient':
                dap_bags_per_acre = 2
            else:
                dap_bags_per_acre = 1.5
            
            total_bags = dap_bags_per_acre * area_acres
            cost = total_bags * 6500  # Rs. 6500 per bag (50kg)
            
            recommendations.append({
                'nutrient': 'Phosphorus',
                'nutrient_urdu': 'فاسفورس',
                'fertilizer': 'DAP (Di-Ammonium Phosphate)',
                'fertilizer_urdu': 'ڈی اے پی',
                'bags_per_acre': dap_bags_per_acre,
                'total_bags': round(total_bags, 1),
                'bag_weight_kg': 50,
                'cost_per_bag': 6500,
                'total_cost': cost,
                'timing': 'Apply at planting time',
                'timing_urdu': 'بوائی کے وقت'
            })
            total_cost += cost
        
        # Potassium (SOP)
        if assessment['potassium']['status'] in ['deficient', 'low']:
            if assessment['potassium']['status'] == 'deficient':
                sop_bags_per_acre = 1.5
            else:
                sop_bags_per_acre = 1
            
            total_bags = sop_bags_per_acre * area_acres
            cost = total_bags * 5000  # Rs. 5000 per bag (50kg)
            
            recommendations.append({
                'nutrient': 'Potassium',
                'nutrient_urdu': 'پوٹاشیم',
                'fertilizer': 'SOP (Sulphate of Potash)',
                'fertilizer_urdu': 'ایس او پی',
                'bags_per_acre': sop_bags_per_acre,
                'total_bags': round(total_bags, 1),
                'bag_weight_kg': 50,
                'cost_per_bag': 5000,
                'total_cost': cost,
                'timing': 'Apply at flowering stage',
                'timing_urdu': 'پھول آنے کے وقت'
            })
            total_cost += cost
        
        # Calculate ROI
        # Fertilizer typically increases yield by 15-25%
        expected_yield_increase = 0.20  # 20% average
        
        # Crop value per acre (rough estimate)
        if crop_type == 'rice':
            base_yield_value = 25 * 40 * 3500  # 25 maunds/acre × 40kg/maund × Rs. 3500/40kg
        else:  # wheat
            base_yield_value = 30 * 40 * 2500
        
        additional_income = base_yield_value * expected_yield_increase
        roi = ((additional_income - total_cost) / total_cost) * 100 if total_cost > 0 else 0
        
        return {
            'recommendations': recommendations,
            'total_investment': round(total_cost, 0),
            'expected_additional_income': round(additional_income, 0),
            'net_benefit': round(additional_income - total_cost, 0),
            'roi_percentage': round(roi, 1)
        }
    
    def format_whatsapp_response(self, assessment, fertilizer_rec, language='urdu'):
        """Format for WhatsApp"""
        if language == 'urdu':
            # Overall health
            health_map = {
                'excellent': '🟢 بہترین',
                'good': '🟡 اچھی',
                'fair': '🟠 درمیانی',
                'poor': '🔴 کمزور'
            }
            health_emoji = health_map.get(assessment['overall_health'], '⚪')
            
            message = f"""
🌱 *مٹی کی صحت*

*مجموعی حالت:* {health_emoji}

📊 *غذائی اجزاء:*
├─ نائٹروجن (N): {assessment['nitrogen']['current']}% ({assessment['nitrogen']['status']})
├─ فاسفورس (P): {assessment['phosphorus']['current']} ppm ({assessment['phosphorus']['status']})
└─ پوٹاشیم (K): {assessment['potassium']['current']} ppm ({assessment['potassium']['status']})
            """.strip()
            
            if fertilizer_rec['recommendations']:
                message += "\n\n💊 *کھاد کی سفارش:*\n"
                
                for rec in fertilizer_rec['recommendations']:
                    message += f"""
├─ *{rec['fertilizer_urdu']}:* {rec['total_bags']:.1f} بوری
   ({rec['bags_per_acre']:.1f} فی ایکڑ)
   قیمت: Rs. {rec['total_cost']:,.0f}
   وقت: {rec['timing_urdu']}
                    """.strip() + "\n"
                
                message += f"""
💰 *کل لاگت:* Rs. {fertilizer_rec['total_investment']:,.0f}
📈 *متوقع اضافی آمدنی:* Rs. {fertilizer_rec['expected_additional_income']:,.0f}
✅ *خالص فائدہ:* Rs. {fertilizer_rec['net_benefit']:,.0f}
📊 *ROI:* {fertilizer_rec['roi_percentage']}%
                """.strip()
            else:
                message += "\n\n✅ مٹی صحت مند ہے۔ ابھی کھاد کی ضرورت نہیں۔"
        
        else:  # English
            health_map = {
                'excellent': '🟢 Excellent',
                'good': '🟡 Good',
                'fair': '🟠 Fair',
                'poor': '🔴 Poor'
            }
            health_emoji = health_map.get(assessment['overall_health'], '⚪')
            
            message = f"""
🌱 *Soil Health Assessment*

*Overall Status:* {health_emoji}

📊 *Nutrients:*
├─ Nitrogen (N): {assessment['nitrogen']['current']}% ({assessment['nitrogen']['status']})
├─ Phosphorus (P): {assessment['phosphorus']['current']} ppm ({assessment['phosphorus']['status']})
└─ Potassium (K): {assessment['potassium']['current']} ppm ({assessment['potassium']['status']})
            """.strip()
            
            if fertilizer_rec['recommendations']:
                message += "\n\n💊 *Fertilizer Recommendations:*\n"
                
                for rec in fertilizer_rec['recommendations']:
                    message += f"""
├─ *{rec['fertilizer']}:* {rec['total_bags']:.1f} bags
   ({rec['bags_per_acre']:.1f} per acre)
   Cost: Rs. {rec['total_cost']:,.0f}
   Timing: {rec['timing']}
                    """.strip() + "\n"
                
                message += f"""
💰 Total Investment: Rs. {fertilizer_rec['total_investment']:,.0f}
📈 Expected Additional Income: Rs. {fertilizer_rec['expected_additional_income']:,.0f}
✅ Net Benefit: Rs. {fertilizer_rec['net_benefit']:,.0f}
📊 ROI: {fertilizer_rec['roi_percentage']}%
                """.strip()
            else:
                message += "\n\n✅ Soil is healthy. No fertilizer needed now."
        
        return message
    
    


if __name__ == "__main__":
    print("="*70)
    print("SOIL HEALTH ANALYZER TEST")
    print("="*70)

    analyzer = SoilHealthAnalyzer()

    # Test 1: Good alluvial soil, 2 years cultivation
    print("\n--- TEST 1: Alluvial Soil, 2 Years ---")
    assessment1 = analyzer.assess_soil_health(
        soil_type='alluvial',
        years_cultivated=2,
        crop_type='rice',
        current_ndvi=0.68
    )
    print(f"Overall health: {assessment1['overall_health']}")
    print(f"Nitrogen: {assessment1['nitrogen']['current']}% ({assessment1['nitrogen']['status']})")
    print(f"Phosphorus: {assessment1['phosphorus']['current']} ppm ({assessment1['phosphorus']['status']})")
    print(f"Potassium: {assessment1['potassium']['current']} ppm ({assessment1['potassium']['status']})")
    
    fertilizer1 = analyzer.recommend_fertilizer(assessment1, 'rice', area_acres=5)
    print(f"\nFertilizer recommendations: {len(fertilizer1['recommendations'])}")
    print(f"Total cost: Rs. {fertilizer1['total_investment']:,.0f}")
    print(f"Expected benefit: Rs. {fertilizer1['net_benefit']:,.0f}")
    
    print("\n📱 WhatsApp Message (Urdu):")
    print("-" * 30)
    print(analyzer.format_whatsapp_response(assessment1, fertilizer1, 'urdu'))
    print("-" * 30)


    # Test 2: Sandy soil, 8 years cultivation (depleted)
    print("\n\n--- TEST 2: Sandy Soil, 8 Years (Depleted) ---")
    assessment2 = analyzer.assess_soil_health(
        soil_type='sandy',
        years_cultivated=8,
        crop_type='wheat',
        current_ndvi=0.42
    )
    print(f"Overall health: {assessment2['overall_health']}")
    
    fertilizer2 = analyzer.recommend_fertilizer(assessment2, 'wheat', area_acres=10)
    print(f"\nFertilizer recommendations: {len(fertilizer2['recommendations'])}")
    
    for rec in fertilizer2['recommendations']:
        print(f"  - {rec['fertilizer']}: {rec['total_bags']:.1f} bags (Rs. {rec['total_cost']:,.0f})")
        
    print(f"\nTotal investment: Rs. {fertilizer2['total_investment']:,.0f}")
    print(f"ROI: {fertilizer2['roi_percentage']}%")
    
    print("\n📱 WhatsApp Message (English):")
    print("-" * 30)
    print(analyzer.format_whatsapp_response(assessment2, fertilizer2, 'english'))
    print("-" * 30)